"""Airfoil analysis endpoints — project-scoped.

Provides both:
  - airfoil_id-based endpoints (looks up polar data from DB Airfoil table)
  - raw-array endpoints (direct polar data in request body)
"""

import asyncio
import logging

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.components import Airfoil
from app.models.project import Project
from app.models.user import User
from app.schemas.airfoil_tools import (
    Correction3DByIdRequest,
    Correction3DByIdResponse,
    Correction3DRequest,
    Correction3DResponse,
    DynamicStallRequest,
    DynamicStallResponse,
    DynStallSimRequest,
    DynStallSimResponse,
    NacaRequest,
    NacaResponse,
    PolarAnalysisByIdRequest,
    PolarAnalysisByIdResponse,
    PolarAnalysisRequest,
    PolarAnalysisResponse,
    WagnerRequest,
    WagnerResponse,
)
from app.services.airfoil_service import (
    analyze_polar,
    apply_3d_correction,
    compute_dynamic_stall_params,
    compute_dynamic_stall_simulation,
    compute_wagner_response,
    generate_naca_profile,
)

logger = logging.getLogger("windforge.airfoil_tools")

router = APIRouter(
    prefix="/projects/{project_id}/airfoil-tools",
    tags=["airfoil-tools"],
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
async def _verify_project(project_id: str, org_id: str, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.org_id == org_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


async def _load_airfoil_polar(
    airfoil_id: str,
    org_id: str,
    db: AsyncSession,
    re: float | None = None,
) -> tuple[list[float], list[float], list[float], list[float]]:
    """Load airfoil polar arrays from DB.

    Returns (alpha, cl, cd, cm) arrays.
    Tries matching by ID first, then by name.
    """
    # Try by ID
    result = await db.execute(
        select(Airfoil).where(Airfoil.id == airfoil_id, Airfoil.org_id == org_id)
    )
    airfoil = result.scalar_one_or_none()

    # Fallback: try by name
    if airfoil is None:
        result = await db.execute(
            select(Airfoil).where(Airfoil.name == airfoil_id, Airfoil.org_id == org_id)
        )
        airfoil = result.scalar_one_or_none()

    if airfoil is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Airfoil '{airfoil_id}' not found",
        )

    if not airfoil.polars or len(airfoil.polars) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Airfoil '{airfoil_id}' has no polar data",
        )

    # Select polar by Reynolds number (or first available)
    polar = airfoil.polars[0]
    if re is not None:
        for p in airfoil.polars:
            if abs(p.get("re", 0) - re) < 1e-3:
                polar = p
                break

    alpha = polar.get("alpha", [])
    cl = polar.get("cl", [])
    cd = polar.get("cd", [])
    cm = polar.get("cm", [0.0] * len(alpha))

    if not alpha or not cl or not cd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Airfoil '{airfoil_id}' polar data is incomplete",
        )

    return alpha, cl, cd, cm


# ---------------------------------------------------------------------------
# Polar analysis by airfoil_id (used by frontend)
# ---------------------------------------------------------------------------
@router.post("/analyze", response_model=PolarAnalysisByIdResponse)
async def analyze_by_id(
    project_id: str,
    body: PolarAnalysisByIdRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Analyze an airfoil polar from DB — returns full arrays for plotting
    plus key parameters (cl_max, alpha_stall, cl_cd_max, alpha_0)."""
    await _verify_project(project_id, current_user.org_id, db)

    alpha, cl, cd, cm = await _load_airfoil_polar(
        body.airfoil_id, current_user.org_id, db, body.re
    )

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: analyze_polar(alpha=alpha, cl=cl, cd=cd, cm=cm),
    )

    # Build cl/cd ratio for plotting
    cd_arr = np.asarray(cd, dtype=float)
    cl_arr = np.asarray(cl, dtype=float)
    cd_safe = np.where(cd_arr > 0, cd_arr, 1e-10)
    cl_cd = (cl_arr / cd_safe).tolist()

    return PolarAnalysisByIdResponse(
        alpha_deg=alpha,
        cl=cl,
        cd=cd,
        cm=cm,
        cl_cd=cl_cd,
        cl_max=result["cl_max"],
        alpha_stall=result["alpha_stall"],
        cl_cd_max=result["cl_cd_max"],
        alpha_0=result["zero_lift_alpha"],
        linear_slope=result["linear_slope"],
    )


# ---------------------------------------------------------------------------
# Polar analysis with raw arrays
# ---------------------------------------------------------------------------
@router.post("/analyze-raw", response_model=PolarAnalysisResponse)
async def analyze_raw(
    project_id: str,
    body: PolarAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Analyze an airfoil polar from raw arrays."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: analyze_polar(
            alpha=body.alpha, cl=body.cl, cd=body.cd, cm=body.cm, re=body.re,
        ),
    )

    return PolarAnalysisResponse(**result)


# ---------------------------------------------------------------------------
# 3-D correction by airfoil_id (used by frontend)
# ---------------------------------------------------------------------------
@router.post("/correction-3d", response_model=Correction3DByIdResponse)
async def correction_3d_by_id(
    project_id: str,
    body: Correction3DByIdRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Apply 3-D rotational correction to an airfoil from DB.
    Returns both original and corrected polars for comparison."""
    await _verify_project(project_id, current_user.org_id, db)

    alpha, cl, cd, _cm = await _load_airfoil_polar(
        body.airfoil_id, current_user.org_id, db
    )

    # Convert c/R to c/r: chord_over_r = c_over_R / r_over_R
    chord_over_r = body.c_over_R / body.r_over_R if body.r_over_R > 0 else 0.1

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: apply_3d_correction(
            alpha=alpha, cl=cl, cd=cd,
            r_over_R=body.r_over_R, chord_over_r=chord_over_r, tsr=body.tsr,
        ),
    )

    return Correction3DByIdResponse(
        alpha_deg=alpha,
        cl_original=cl,
        cd_original=cd,
        cl_corrected=result["cl_corrected"],
        cd_corrected=result["cd_corrected"],
    )


# ---------------------------------------------------------------------------
# 3-D correction with raw arrays
# ---------------------------------------------------------------------------
@router.post("/correction-3d-raw", response_model=Correction3DResponse)
async def correction_3d_raw(
    project_id: str,
    body: Correction3DRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Apply 3-D rotational correction (Du-Selig) to a 2-D airfoil polar."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: apply_3d_correction(
            alpha=body.alpha, cl=body.cl, cd=body.cd,
            r_over_R=body.r_over_R, chord_over_r=body.chord_over_r, tsr=body.tsr,
        ),
    )

    return Correction3DResponse(**result)


# ---------------------------------------------------------------------------
# Dynamic stall parameters
# ---------------------------------------------------------------------------
@router.post("/dynamic-stall", response_model=DynamicStallResponse)
async def dynamic_stall(
    project_id: str,
    body: DynamicStallRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Extract MHH and Oye dynamic stall model parameters from a polar."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: compute_dynamic_stall_params(
            alpha=body.alpha, cl=body.cl, cd=body.cd,
            cm=body.cm, chord=body.chord, tau_oye=body.tau_oye,
        ),
    )

    return DynamicStallResponse(**result)


# ---------------------------------------------------------------------------
# NACA profile generation
# ---------------------------------------------------------------------------
@router.post("/generate-naca", response_model=NacaResponse)
async def generate_naca(
    project_id: str,
    body: NacaRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate NACA 4-digit airfoil profile coordinates."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: generate_naca_profile(
            digits=body.digits, n_points=body.n_points,
        ),
    )

    return NacaResponse(**result)


# ---------------------------------------------------------------------------
# Dynamic stall simulation (Cl-α hysteresis)
# ---------------------------------------------------------------------------
@router.post("/dynamic-stall-sim", response_model=DynStallSimResponse)
async def dynamic_stall_sim(
    project_id: str,
    body: DynStallSimRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Simulate dynamic stall hysteresis loop (Oye model)."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: compute_dynamic_stall_simulation(
            alpha=body.alpha, cl=body.cl, cd=body.cd, cm=body.cm,
            chord=body.chord, U0=body.U0,
            mean_alpha_deg=body.mean_alpha_deg,
            amplitude_deg=body.amplitude_deg,
            freq=body.freq, n_cycles=body.n_cycles,
        ),
    )

    return DynStallSimResponse(**result)


# ---------------------------------------------------------------------------
# Wagner indicial lift function
# ---------------------------------------------------------------------------
@router.post("/wagner", response_model=WagnerResponse)
async def wagner_response(
    project_id: str,
    body: WagnerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute Wagner indicial lift function (Jones vs OpenFAST)."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: compute_wagner_response(
            s_max=body.s_max, n_points=body.n_points,
        ),
    )

    return WagnerResponse(**result)
