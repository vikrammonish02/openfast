"""System dynamics endpoints -- project-scoped."""

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
from app.schemas.dynamics import (
    BodePlotRequest, BodePlotResponse,
    ForcedVibrationRequest, ForcedVibrationResponse,
    LorenzRequest, LorenzResponse,
    PendulumRequest, PendulumResponse,
    StepImpulseRequest, StepImpulseResponse,
)
from app.services.dynamics_service import (
    compute_bode_plot,
    compute_forced_vibration,
    compute_lorenz_attractor,
    compute_pendulum,
    compute_step_impulse_response,
)

logger = logging.getLogger("windforge.dynamics")

router = APIRouter(prefix="/projects/{project_id}/dynamics", tags=["dynamics"])


async def _verify_project(project_id: str, org_id: str, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.org_id == org_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.post("/forced-vibration", response_model=ForcedVibrationResponse)
async def forced_vibration(
    project_id: str, body: ForcedVibrationRequest,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Compute SDOF forced vibration frequency response via welib."""
    await _verify_project(project_id, current_user.org_id, db)
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, partial(
        compute_forced_vibration, zeta_values=body.zeta_values,
        frat_min=body.frat_min, frat_max=body.frat_max, n_points=body.n_points,
    ))
    return ForcedVibrationResponse(**result)


@router.post("/bode-plot", response_model=BodePlotResponse)
async def bode_plot(
    project_id: str, body: BodePlotRequest,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Compute Bode plot for a mass-spring-damper system via welib."""
    await _verify_project(project_id, current_user.org_id, db)
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, partial(
        compute_bode_plot, mass=body.mass, damping=body.damping, stiffness=body.stiffness,
        freq_min=body.freq_min, freq_max=body.freq_max, n_points=body.n_points,
    ))
    return BodePlotResponse(**result)


@router.post("/step-impulse", response_model=StepImpulseResponse)
async def step_impulse(
    project_id: str, body: StepImpulseRequest,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Compute step/impulse/ramp response of SDOF system."""
    await _verify_project(project_id, current_user.org_id, db)
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, partial(
        compute_step_impulse_response, mass=body.mass, damping=body.damping,
        stiffness=body.stiffness, response_type=body.response_type,
        t_max=body.t_max, dt=body.dt,
    ))
    return StepImpulseResponse(**result)


@router.post("/lorenz", response_model=LorenzResponse)
async def lorenz(
    project_id: str, body: LorenzRequest,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Integrate Lorenz attractor via welib."""
    await _verify_project(project_id, current_user.org_id, db)
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, partial(
        compute_lorenz_attractor, sigma=body.sigma, rho=body.rho, beta=body.beta,
        x0=body.x0, y0=body.y0, z0=body.z0, t_max=body.t_max, dt=body.dt,
    ))
    return LorenzResponse(**result)


@router.post("/pendulum", response_model=PendulumResponse)
async def pendulum(
    project_id: str, body: PendulumRequest,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Simulate pendulum dynamics."""
    await _verify_project(project_id, current_user.org_id, db)
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, partial(
        compute_pendulum, length=body.length, mass=body.mass,
        damping_ratio=body.damping_ratio, theta0=body.theta0, omega0=body.omega0,
        t_max=body.t_max, dt=body.dt,
    ))
    return PendulumResponse(**result)
