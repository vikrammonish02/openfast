"""Particle dynamics endpoints -- project-scoped."""

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
from app.schemas.particle import (
    FreeFallRequest,
    FreeFallResponse,
    OrbitRequest,
    OrbitResponse,
    SpringMassRequest,
    SpringMassResponse,
)
from app.services.particle_service import (
    compute_free_fall,
    compute_spring_mass,
    compute_two_body_orbit,
)

logger = logging.getLogger("windforge.particles")

router = APIRouter(
    prefix="/projects/{project_id}/particles",
    tags=["particles"],
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
@router.post("/free-fall", response_model=FreeFallResponse)
async def free_fall(
    project_id: str,
    body: FreeFallRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Simulate projectile free-fall under gravity."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        partial(
            compute_free_fall,
            mass=body.mass, z0=body.z0, vx0=body.vx0, vz0=body.vz0,
            g=body.g, t_max=body.t_max, n_points=body.n_points,
        ),
    )
    return FreeFallResponse(**result)


@router.post("/orbit", response_model=OrbitResponse)
async def orbit(
    project_id: str,
    body: OrbitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Simulate two-body gravitational orbital motion."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        partial(
            compute_two_body_orbit,
            m1=body.m1, m2=body.m2, r_initial=body.r_initial,
            eccentricity=body.eccentricity, n_orbits=body.n_orbits,
            n_points=body.n_points,
        ),
    )
    return OrbitResponse(**result)


@router.post("/spring-mass", response_model=SpringMassResponse)
async def spring_mass(
    project_id: str,
    body: SpringMassRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Simulate spring-mass system with optional damping."""
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        partial(
            compute_spring_mass,
            m=body.m, k=body.k, c=body.c, z0_offset=body.z0_offset,
            g=body.g, t_max=body.t_max, n_points=body.n_points,
        ),
    )
    return SpringMassResponse(**result)
