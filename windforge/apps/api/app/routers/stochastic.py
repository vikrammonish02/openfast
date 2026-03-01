"""Stochastic & signal processing endpoints -- project-scoped."""

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
from app.schemas.stochastic import (
    CorrelationRequest,
    CorrelationResponse,
    DistributionsRequest,
    DistributionsResponse,
    FftPsdRequest,
    FftPsdResponse,
    StochasticProcessRequest,
    StochasticProcessResponse,
    TurbulentWindRequest,
    TurbulentWindResponse,
)
from app.services.stochastic_service import (
    compute_correlation,
    compute_distributions,
    compute_fft_psd,
    compute_stochastic_process,
    generate_turbulent_wind,
)

logger = logging.getLogger("windforge.stochastic")

router = APIRouter(
    prefix="/projects/{project_id}/stochastic",
    tags=["stochastic"],
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
@router.post("/distributions", response_model=DistributionsResponse)
async def distributions(
    project_id: str,
    body: DistributionsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute probability distribution PDFs."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        partial(
            compute_distributions,
            distributions=body.distributions,
            x_min=body.x_min,
            x_max=body.x_max,
            n_points=body.n_points,
        ),
    )
    return DistributionsResponse(**result)


@router.post("/process", response_model=StochasticProcessResponse)
async def stochastic_process(
    project_id: str,
    body: StochasticProcessRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sample a stationary stochastic process."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        partial(
            compute_stochastic_process,
            process_type=body.process_type,
            omega_max=body.omega_max,
            tau_max=body.tau_max,
            time_max=body.time_max,
            n_discr=body.n_discr,
        ),
    )
    return StochasticProcessResponse(**result)


@router.post("/fft-psd", response_model=FftPsdResponse)
async def fft_psd(
    project_id: str,
    body: FftPsdRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute FFT amplitude or PSD of a signal."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        partial(
            compute_fft_psd,
            time=body.time,
            signal=body.signal,
            output_type=body.output_type,
            averaging=body.averaging,
        ),
    )
    return FftPsdResponse(**result)


@router.post("/correlation", response_model=CorrelationResponse)
async def correlation(
    project_id: str,
    body: CorrelationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate correlated signals and compute auto-correlation."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        partial(
            compute_correlation,
            coeff=body.coeff,
            n_points=body.n_points,
            n_lags=body.n_lags,
        ),
    )
    return CorrelationResponse(**result)


@router.post("/turbulent-wind", response_model=TurbulentWindResponse)
async def turbulent_wind(
    project_id: str,
    body: TurbulentWindRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate synthetic turbulent wind time series using Kaimal spectrum."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        partial(
            generate_turbulent_wind,
            U0=body.U0,
            turbulence_intensity=body.turbulence_intensity,
            L=body.L,
            t_max=body.t_max,
            dt=body.dt,
            seed=body.seed,
        ),
    )
    return TurbulentWindResponse(**result)
