"""Hydrodynamics endpoints -- project-scoped."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.project import Project
from app.models.user import User
from app.schemas.hydro import (
    HydrostaticRequest,
    HydrostaticResponse,
    JonswapRequest,
    JonswapResponse,
    MorisonRequest,
    MorisonResponse,
    WaveKinematicsRequest,
    WaveKinematicsResponse,
)
from app.services.hydro_service import (
    compute_hydrostatic_properties,
    compute_jonswap_spectrum,
    compute_morison_loads,
    compute_wave_kinematics,
)

logger = logging.getLogger("windforge.hydro")

router = APIRouter(
    prefix="/projects/{project_id}/hydro",
    tags=["hydro"],
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
@router.post("/wave-kinematics", response_model=WaveKinematicsResponse)
async def wave_kinematics(
    project_id: str,
    body: WaveKinematicsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute wave kinematics (elevation, velocity, acceleration) from a
    JONSWAP spectrum using linear Airy wave theory via welib."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        compute_wave_kinematics,
        body.Hs,
        body.Tp,
        body.water_depth,
        body.time_duration,
        body.n_freq,
        None,  # z_positions (use defaults)
    )

    return WaveKinematicsResponse(**result)


@router.post("/jonswap-spectrum", response_model=JonswapResponse)
async def jonswap_spectrum(
    project_id: str,
    body: JonswapRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute a JONSWAP spectral density curve via welib."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        compute_jonswap_spectrum,
        body.Hs,
        body.Tp,
        body.freq_min,
        body.freq_max,
        body.n_points,
    )

    return JonswapResponse(**result)


@router.post("/morison-loads", response_model=MorisonResponse)
async def morison_loads(
    project_id: str,
    body: MorisonRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute Morison inline loads on a monopile via welib."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        compute_morison_loads,
        body.Hs,
        body.Tp,
        body.water_depth,
        body.monopile_diameter,
        body.Cd,
        body.Cm,
        body.time_duration,
        body.n_freq,
    )

    return MorisonResponse(**result)


@router.post("/hydrostatic", response_model=HydrostaticResponse)
async def hydrostatic(
    project_id: str,
    body: HydrostaticRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute hydrostatic restoring and added-mass matrices for a
    vertical cylinder via welib."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        compute_hydrostatic_properties,
        body.radius,
        body.z_bottom,
        body.z_top,
        body.rho_water,
        body.mass_structure,
        body.z_cg,
    )

    return HydrostaticResponse(**result)
