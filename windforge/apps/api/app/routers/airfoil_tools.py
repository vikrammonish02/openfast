"""Airfoil analysis endpoints — project-scoped."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.project import Project
from app.models.user import User
from app.schemas.airfoil_tools import (
    Correction3DRequest,
    Correction3DResponse,
    DynamicStallRequest,
    DynamicStallResponse,
    NacaRequest,
    NacaResponse,
    PolarAnalysisRequest,
    PolarAnalysisResponse,
)
from app.services.airfoil_service import (
    analyze_polar,
    apply_3d_correction,
    compute_dynamic_stall_params,
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


# ---------------------------------------------------------------------------
# endpoints
# ---------------------------------------------------------------------------
@router.post("/analyze", response_model=PolarAnalysisResponse)
async def analyze(
    project_id: str,
    body: PolarAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Analyze an airfoil polar to extract key aerodynamic parameters.

    Returns cl_max, stall angle, max L/D, zero-lift alpha, linear slope,
    and AeroDyn unsteady aerodynamic parameters.
    """
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: analyze_polar(
            alpha=body.alpha,
            cl=body.cl,
            cd=body.cd,
            cm=body.cm,
            re=body.re,
        ),
    )

    return PolarAnalysisResponse(**result)


@router.post("/correction-3d", response_model=Correction3DResponse)
async def correction_3d(
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
            alpha=body.alpha,
            cl=body.cl,
            cd=body.cd,
            r_over_R=body.r_over_R,
            chord_over_r=body.chord_over_r,
            tsr=body.tsr,
        ),
    )

    return Correction3DResponse(**result)


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
            alpha=body.alpha,
            cl=body.cl,
            cd=body.cd,
            cm=body.cm,
            chord=body.chord,
            tau_oye=body.tau_oye,
        ),
    )

    return DynamicStallResponse(**result)


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
            digits=body.digits,
            n_points=body.n_points,
        ),
    )

    return NacaResponse(**result)
