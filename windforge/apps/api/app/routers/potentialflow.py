"""Potential flow & vortex element endpoints -- project-scoped."""

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
from app.schemas.potentialflow import (
    CylinderFlowRequest,
    CylinderFlowResponse,
    KarmanTrefftzRequest,
    KarmanTrefftzResponse,
    VortexPointRequest,
    VortexPointResponse,
)
from app.services.potentialflow_service import (
    compute_cylinder_flow,
    compute_karman_trefftz,
    compute_vortex_point_flow,
)

logger = logging.getLogger("windforge.potentialflow")

router = APIRouter(
    prefix="/projects/{project_id}/potential-flow",
    tags=["potential-flow"],
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
@router.post("/vortex-point", response_model=VortexPointResponse)
async def vortex_point(
    project_id: str,
    body: VortexPointRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute 2D vortex point velocity field and stream function."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        partial(
            compute_vortex_point_flow,
            Gamma=body.Gamma,
            x_min=body.x_min,
            x_max=body.x_max,
            y_min=body.y_min,
            y_max=body.y_max,
            n_grid=body.n_grid,
            vortex_x=body.vortex_x,
            vortex_y=body.vortex_y,
        ),
    )
    return VortexPointResponse(**result)


@router.post("/cylinder-flow", response_model=CylinderFlowResponse)
async def cylinder_flow(
    project_id: str,
    body: CylinderFlowRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute 2D flow around a cylinder with optional circulation."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        partial(
            compute_cylinder_flow,
            U0=body.U0,
            R=body.R,
            Gamma=body.Gamma,
            alpha_deg=body.alpha_deg,
            x_min=body.x_min,
            x_max=body.x_max,
            y_min=body.y_min,
            y_max=body.y_max,
            n_grid=body.n_grid,
            n_theta=body.n_theta,
        ),
    )
    return CylinderFlowResponse(**result)


@router.post("/karman-trefftz", response_model=KarmanTrefftzResponse)
async def karman_trefftz(
    project_id: str,
    body: KarmanTrefftzRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute Karman-Trefftz airfoil shape, flow field, and surface Cp."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        partial(
            compute_karman_trefftz,
            XC=body.XC,
            YC=body.YC,
            tau_deg=body.tau_deg,
            alpha_deg=body.alpha_deg,
            U0=body.U0,
            A=body.A,
            n_surface=body.n_surface,
            n_grid=body.n_grid,
        ),
    )
    return KarmanTrefftzResponse(**result)
