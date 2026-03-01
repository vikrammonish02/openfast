"""Fatigue analysis endpoints — project-scoped."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.project import Project
from app.models.simulation import Simulation, SimulationCase
from app.models.user import User
from app.schemas.fatigue import (
    EquivalentLoadDirectRequest,
    EquivalentLoadDirectResponse,
    EquivalentLoadRequest,
    EquivalentLoadResponse,
    RainflowRequest,
    RainflowResponse,
)
from app.services.fatigue_service import (
    compute_equivalent_load,
    compute_rainflow_cycles,
    load_time_series_from_file,
)

logger = logging.getLogger("windforge.fatigue")

router = APIRouter(
    prefix="/projects/{project_id}/fatigue",
    tags=["fatigue"],
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


async def _get_output_file_path(
    simulation_id: str,
    case_id: str,
    project_id: str,
    db: AsyncSession,
) -> str:
    """Look up the simulation case and return the output file path."""
    result = await db.execute(
        select(SimulationCase).join(Simulation).where(
            SimulationCase.id == case_id,
            SimulationCase.simulation_id == simulation_id,
            Simulation.project_id == project_id,
        )
    )
    case = result.scalar_one_or_none()
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation case not found",
        )

    if case.input_files is None or "output_file" not in case.input_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No output file available for this simulation case. Run the simulation first.",
        )

    return case.input_files["output_file"]


# ---------------------------------------------------------------------------
# endpoints
# ---------------------------------------------------------------------------
@router.post("/equivalent-load", response_model=EquivalentLoadResponse)
async def equivalent_load_from_sim(
    project_id: str,
    body: EquivalentLoadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute damage equivalent loads from a simulation case output file."""
    await _verify_project(project_id, current_user.org_id, db)

    output_file = await _get_output_file_path(
        body.simulation_id, body.case_id, project_id, db,
    )

    loop = asyncio.get_running_loop()

    # Load time series from file (CPU-bound I/O)
    time_arr, signal_arr = await loop.run_in_executor(
        None,
        lambda: load_time_series_from_file(output_file, body.channel),
    )

    # Compute DEL
    result = await loop.run_in_executor(
        None,
        lambda: compute_equivalent_load(
            time_arr, signal_arr,
            m_exponents=body.m_exponents,
            Teq=body.Teq,
        ),
    )

    return EquivalentLoadResponse(channel=body.channel, **result)


@router.post("/equivalent-load-direct", response_model=EquivalentLoadDirectResponse)
async def equivalent_load_direct(
    project_id: str,
    body: EquivalentLoadDirectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute damage equivalent loads from directly-provided time series data."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: compute_equivalent_load(
            body.time, body.signal,
            m_exponents=body.m_exponents,
            Teq=body.Teq,
        ),
    )

    return EquivalentLoadDirectResponse(**result)


@router.post("/rainflow", response_model=RainflowResponse)
async def rainflow_cycles(
    project_id: str,
    body: RainflowRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute rainflow cycle counts from a simulation case output file."""
    await _verify_project(project_id, current_user.org_id, db)

    output_file = await _get_output_file_path(
        body.simulation_id, body.case_id, project_id, db,
    )

    loop = asyncio.get_running_loop()

    # Load time series from file
    time_arr, signal_arr = await loop.run_in_executor(
        None,
        lambda: load_time_series_from_file(output_file, body.channel),
    )

    # Compute rainflow
    result = await loop.run_in_executor(
        None,
        lambda: compute_rainflow_cycles(time_arr, signal_arr),
    )

    return RainflowResponse(channel=body.channel, **result)
