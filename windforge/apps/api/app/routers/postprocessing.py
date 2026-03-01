"""Post-processing endpoints -- project-scoped.

All computation delegates to openfast_toolbox validated functions
via the postprocessing_service module.
"""

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
from app.schemas.postprocessing import (
    DelFatigueRequest,
    DelFatigueResponse,
    StatisticsRequest,
    StatisticsResponse,
    SpectralRequest,
    SpectralResponse,
    DampingRequest,
    DampingResponse,
)
from app.services.postprocessing_service import (
    compute_del_fatigue,
    compute_statistics,
    compute_spectral,
    compute_damping,
)

logger = logging.getLogger("windforge.postprocessing")

router = APIRouter(
    prefix="/projects/{project_id}/postprocessing",
    tags=["postprocessing"],
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
@router.post("/del-fatigue", response_model=DelFatigueResponse)
async def del_fatigue(
    project_id: str,
    body: DelFatigueRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute DEL and Markov cycle matrix from a synthetic load signal.

    Uses openfast_toolbox.tools.fatigue (equivalent_load, cycle_matrix, rainflow).
    """
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        partial(
            compute_del_fatigue,
            signal_type=body.signal_type,
            amplitude=body.amplitude,
            frequency=body.frequency,
            noise_std=body.noise_std,
            mean_load=body.mean_load,
            duration=body.duration,
            dt=body.dt,
            wohler_exponents=body.wohler_exponents,
            n_bins=body.n_bins,
            rainflow_method=body.rainflow_method,
        ),
    )
    return DelFatigueResponse(**result)


@router.post("/statistics", response_model=StatisticsResponse)
async def statistics(
    project_id: str,
    body: StatisticsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute PDF and basic statistics of a signal.

    Uses openfast_toolbox.tools.stats (pdf).
    """
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        partial(
            compute_statistics,
            signal_type=body.signal_type,
            amplitude=body.amplitude,
            frequency=body.frequency,
            noise_std=body.noise_std,
            mean_val=body.mean_val,
            duration=body.duration,
            dt=body.dt,
            pdf_method=body.pdf_method,
            n_bins=body.n_bins,
        ),
    )
    return StatisticsResponse(**result)


@router.post("/spectral", response_model=SpectralResponse)
async def spectral(
    project_id: str,
    body: SpectralRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute FFT/PSD of a multi-component signal.

    Uses openfast_toolbox.tools.spectral (fft_wrap).
    """
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        partial(
            compute_spectral,
            signal_type=body.signal_type,
            frequencies=body.frequencies,
            amplitudes=body.amplitudes,
            noise_std=body.noise_std,
            duration=body.duration,
            dt=body.dt,
            output_type=body.output_type,
            averaging=body.averaging,
            averaging_window=body.averaging_window,
        ),
    )
    return SpectralResponse(**result)


@router.post("/damping", response_model=DampingResponse)
async def damping(
    project_id: str,
    body: DampingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Estimate natural frequency and damping ratio from a decaying signal.

    Uses openfast_toolbox.tools.damping (freqDampFromPeaks).
    """
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        partial(
            compute_damping,
            natural_freq=body.natural_freq,
            damping_ratio=body.damping_ratio,
            amplitude=body.amplitude,
            mean_offset=body.mean_offset,
            duration=body.duration,
            dt=body.dt,
        ),
    )
    return DampingResponse(**result)
