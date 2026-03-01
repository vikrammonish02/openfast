"""Wind environment analysis endpoints — project-scoped."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.project import Project
from app.models.user import User
from app.schemas.wind import (
    EOGRequest,
    EOGResponse,
    KaimalRequest,
    KaimalResponse,
    TurbulenceEnvelopeRequest,
    TurbulenceEnvelopeResponse,
    WindShearRequest,
    WindShearResponse,
)
from app.services.wind_service import (
    compute_eog,
    compute_kaimal_spectrum,
    compute_turbulence_envelope,
    compute_wind_shear,
)

logger = logging.getLogger("windforge.wind")

router = APIRouter(
    prefix="/projects/{project_id}/wind",
    tags=["wind"],
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
@router.post("/kaimal-spectrum", response_model=KaimalResponse)
async def kaimal_spectrum(
    project_id: str,
    body: KaimalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute Kaimal turbulence spectrum for u, v, w components."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: compute_kaimal_spectrum(
            V_hub=body.V_hub,
            freq_min=body.freq_min,
            freq_max=body.freq_max,
            n_points=body.n_points,
            turbulence_class=body.turbulence_class,
        ),
    )

    return KaimalResponse(**result)


@router.post("/turbulence-envelope", response_model=TurbulenceEnvelopeResponse)
async def turbulence_envelope(
    project_id: str,
    body: TurbulenceEnvelopeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute NTM/ETM turbulence standard-deviation envelopes for IEC classes A, B, C."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: compute_turbulence_envelope(
            wind_class=body.wind_class,
            v_ref=body.v_ref,
        ),
    )

    return TurbulenceEnvelopeResponse(**result)


@router.post("/eog", response_model=EOGResponse)
async def eog(
    project_id: str,
    body: EOGRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute IEC Extreme Operating Gust (EOG) time series."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: compute_eog(
            V_hub=body.V_hub,
            rotor_diameter=body.rotor_diameter,
            hub_height=body.hub_height,
            wind_class=body.wind_class,
            turbulence_class=body.turbulence_class,
        ),
    )

    return EOGResponse(**result)


@router.post("/wind-shear", response_model=WindShearResponse)
async def wind_shear(
    project_id: str,
    body: WindShearRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute power-law and log-law wind shear profiles."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: compute_wind_shear(
            V_hub=body.V_hub,
            hub_height=body.hub_height,
            shear_exp=body.shear_exp,
            z0=body.z0,
            z_min=body.z_min,
            z_max=body.z_max,
            n_points=body.n_points,
        ),
    )

    return WindShearResponse(**result)
