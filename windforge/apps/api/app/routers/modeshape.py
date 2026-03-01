"""Mode shape analysis endpoints — project-scoped."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.components import Blade, Tower, TurbineModel
from app.models.project import Project
from app.models.user import User
from app.schemas.modeshape import (
    DeflectionRequest,
    DeflectionResponse,
    ModeData,
    ModeShapeRequest,
    ModeShapeResponse,
)
from app.services.modeshape_service import (
    compute_blade_mode_shapes,
    compute_static_deflection,
    compute_tower_mode_shapes,
)

logger = logging.getLogger("windforge.modeshape")

router = APIRouter(
    prefix="/projects/{project_id}/modeshape",
    tags=["modeshape"],
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
async def _verify_project(project_id: str, org_id: str, db: AsyncSession) -> Project:
    """Verify project exists and belongs to the user's organisation."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.org_id == org_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return project


async def _load_turbine_context(
    turbine_model_id: str, project_id: str, db: AsyncSession
) -> tuple[TurbineModel, Tower | None, Blade | None]:
    """Load turbine model with its tower and blade from DB."""
    result = await db.execute(
        select(TurbineModel).where(
            TurbineModel.id == turbine_model_id,
            TurbineModel.project_id == project_id,
        )
    )
    tm = result.scalar_one_or_none()
    if tm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Turbine model not found"
        )

    tower = None
    if tm.tower_id:
        t_result = await db.execute(select(Tower).where(Tower.id == tm.tower_id))
        tower = t_result.scalar_one_or_none()

    blade = None
    if tm.blade_id:
        b_result = await db.execute(select(Blade).where(Blade.id == tm.blade_id))
        blade = b_result.scalar_one_or_none()

    return tm, tower, blade


# ---------------------------------------------------------------------------
# endpoints
# ---------------------------------------------------------------------------
@router.post("/compute", response_model=ModeShapeResponse)
async def compute_mode_shapes(
    project_id: str,
    body: ModeShapeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute mode shapes for a tower or blade component."""
    await _verify_project(project_id, current_user.org_id, db)
    tm, tower, blade = await _load_turbine_context(
        body.turbine_model_id, project_id, db
    )

    loop = asyncio.get_running_loop()

    if body.component == "tower":
        if tower is None or not tower.stations:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tower not found or has no stations.",
            )

        # Compute RNA mass for tip-mass option
        tip_mass = 0.0
        if body.include_tip_mass:
            hub_mass = tm.hub_mass or 0.0
            nacelle_mass = tm.nacelle_mass or 0.0
            tip_mass = hub_mass + nacelle_mass

        result = await loop.run_in_executor(
            None,
            compute_tower_mode_shapes,
            tower.stations,
            tower.tower_height,
            tip_mass,
            body.n_modes,
        )

        modes = [
            ModeData(
                frequency=m["frequency"],
                label=m["label"],
                shape_values=m["shape_values"],
            )
            for m in result["modes"]
        ]
        return ModeShapeResponse(
            component="tower",
            span_positions=result["span_positions"],
            modes=modes,
        )

    elif body.component == "blade":
        if blade is None or not blade.structural_stations:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Blade not found or has no structural stations.",
            )

        result = await loop.run_in_executor(
            None,
            compute_blade_mode_shapes,
            blade.structural_stations,
            blade.blade_length,
            body.n_modes,
        )

        modes = [
            ModeData(
                frequency=m["frequency"],
                label=m["label"],
                shape_values=m.get("flap_shape", []),
                shape_values_edge=m.get("edge_shape"),
            )
            for m in result["modes"]
        ]
        return ModeShapeResponse(
            component="blade",
            span_positions=result["span_positions"],
            modes=modes,
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown component '{body.component}'. Must be 'tower' or 'blade'.",
        )


@router.post("/deflection", response_model=DeflectionResponse)
async def compute_deflection(
    project_id: str,
    body: DeflectionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute static deflection for a tower or blade component."""
    await _verify_project(project_id, current_user.org_id, db)
    tm, tower, blade = await _load_turbine_context(
        body.turbine_model_id, project_id, db
    )

    loop = asyncio.get_running_loop()

    if body.component == "tower":
        if tower is None or not tower.stations:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tower not found or has no stations.",
            )
        result = await loop.run_in_executor(
            None,
            compute_static_deflection,
            tower.stations,
            tower.tower_height,
            body.tip_load,
            body.distributed_load,
        )

    elif body.component == "blade":
        if blade is None or not blade.structural_stations:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Blade not found or has no structural stations.",
            )
        result = await loop.run_in_executor(
            None,
            compute_static_deflection,
            blade.structural_stations,
            blade.blade_length,
            body.tip_load,
            body.distributed_load,
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown component '{body.component}'. Must be 'tower' or 'blade'.",
        )

    return DeflectionResponse(
        span_positions=result["span_positions"],
        deflection=result["deflection"],
    )
