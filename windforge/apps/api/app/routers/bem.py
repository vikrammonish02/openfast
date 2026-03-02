"""BEM & Rotor aerodynamics endpoints -- project-scoped."""

import asyncio
import logging
from functools import partial

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.project import Project
from app.models.user import User
from app.schemas.bem import (
    CpSurfaceRequest,
    CpSurfaceResponse,
    DynamicInflowRequest,
    DynamicInflowResponse,
    HighThrustRequest,
    HighThrustResponse,
    IdealRotorRequest,
    IdealRotorResponse,
    OptimalCpRequest,
    OptimalCpResponse,
    PowerCurveRequest,
    PowerCurveResponse,
    WakeExpansionRequest,
    WakeExpansionResponse,
)
from app.services.bem_service import (
    compute_cp_lambda_pitch_surface,
    compute_dynamic_inflow,
    compute_high_thrust_corrections,
    compute_ideal_rotor_planform,
    compute_optimal_cp_betz,
    compute_power_curve,
    compute_wake_expansion,
)

logger = logging.getLogger("windforge.bem")

router = APIRouter(
    prefix="/projects/{project_id}/bem",
    tags=["bem"],
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
@router.post("/cp-surface", response_model=CpSurfaceResponse)
async def cp_surface(
    project_id: str,
    body: CpSurfaceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute CP-lambda-pitch 3D surface via welib BEM."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        partial(
            compute_cp_lambda_pitch_surface,
            r=body.r,
            chord=body.chord,
            twist=body.twist,
            polar_alpha=body.polar_alpha,
            polar_cl=body.polar_cl,
            polar_cd=body.polar_cd,
            V0=body.V0,
            nB=body.nB,
            cone=body.cone,
            R=body.R,
            tsr_min=body.tsr_min,
            tsr_max=body.tsr_max,
            tsr_steps=body.tsr_steps,
            pitch_min=body.pitch_min,
            pitch_max=body.pitch_max,
            pitch_steps=body.pitch_steps,
        ),
    )
    return CpSurfaceResponse(**result)


@router.post("/power-curve", response_model=PowerCurveResponse)
async def power_curve(
    project_id: str,
    body: PowerCurveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute aerodynamic power curve via welib BEM."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        partial(
            compute_power_curve,
            r=body.r,
            chord=body.chord,
            twist=body.twist,
            polar_alpha=body.polar_alpha,
            polar_cl=body.polar_cl,
            polar_cd=body.polar_cd,
            R=body.R,
            nB=body.nB,
            cone=body.cone,
            rpm=body.rpm,
            pitch=body.pitch,
            wind_speeds=body.wind_speeds,
        ),
    )
    return PowerCurveResponse(**result)


@router.post("/high-thrust", response_model=HighThrustResponse)
async def high_thrust(
    project_id: str,
    body: HighThrustRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compare Ct vs a for multiple high-thrust correction methods."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        partial(
            compute_high_thrust_corrections,
            methods=body.methods,
            a_min=body.a_min,
            a_max=body.a_max,
            n_points=body.n_points,
        ),
    )
    return HighThrustResponse(**result)


@router.post("/ideal-rotor", response_model=IdealRotorResponse)
async def ideal_rotor(
    project_id: str,
    body: IdealRotorRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute ideal rotor chord and twist distributions via welib."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        partial(
            compute_ideal_rotor_planform,
            R=body.R,
            r_hub=body.r_hub,
            TSR_design=body.TSR_design,
            Cl_design=body.Cl_design,
            B=body.B,
            n_points=body.n_points,
        ),
    )
    return IdealRotorResponse(**result)


@router.post("/optimal-cp", response_model=OptimalCpResponse)
async def optimal_cp(
    project_id: str,
    body: OptimalCpRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute optimal CP vs TSR (actuator disc momentum theory) via welib."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        partial(
            compute_optimal_cp_betz,
            tsr_min=body.tsr_min,
            tsr_max=body.tsr_max,
            n_points=body.n_points,
        ),
    )
    return OptimalCpResponse(**result)


@router.post("/wake-expansion", response_model=WakeExpansionResponse)
async def wake_expansion_endpoint(
    project_id: str,
    body: WakeExpansionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute wake expansion r/R vs downstream distance via welib."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        partial(
            compute_wake_expansion,
            CT=body.CT,
            models=body.models,
            x_max_over_D=body.x_max_over_D,
            n_points=body.n_points,
        ),
    )
    return WakeExpansionResponse(**result)


@router.post("/dynamic-inflow", response_model=DynamicInflowResponse)
async def dynamic_inflow(
    project_id: str,
    body: DynamicInflowRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Simulate Øye dynamic inflow step response via welib."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        partial(
            compute_dynamic_inflow,
            R=body.R,
            U0=body.U0,
            a_init=body.a_init,
            a_final=body.a_final,
            r_bar=body.r_bar,
            t_max=body.t_max,
            dt=body.dt,
        ),
    )
    return DynamicInflowResponse(**result)
