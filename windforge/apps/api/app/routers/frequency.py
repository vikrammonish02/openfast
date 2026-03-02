"""Structural frequency analysis endpoints — project-scoped."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models.components import Blade, Tower, TurbineModel
from app.models.project import Project
from app.models.user import User
from app.schemas.frequency import (
    CampbellRequest,
    CampbellResponse,
    FrequencyRequest,
    FrequencyResponse,
    MultiStageRequest,
    MultiStageResponse,
)
from app.services.frequency_service import (
    STAGE_LABELS,
    compute_campbell_diagram,
    compute_combined_frequencies,
)

logger = logging.getLogger("windforge.frequency")

router = APIRouter(
    prefix="/projects/{project_id}/frequency",
    tags=["frequency"],
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


async def _load_turbine_context(
    turbine_model_id: str, project_id: str, db: AsyncSession
) -> tuple[dict | None, dict | None, dict]:
    """Load tower data, blade data, and turbine model dict from DB."""
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

    # Load tower
    tower_data = None
    if tm.tower_id:
        t_result = await db.execute(select(Tower).where(Tower.id == tm.tower_id))
        tower = t_result.scalar_one_or_none()
        if tower:
            tower_data = {
                "stations": tower.stations or [],
                "tower_height": tower.tower_height,
                "damping": {
                    "fa_1": tower.tower_fa_damping_1,
                    "fa_2": tower.tower_fa_damping_2,
                    "ss_1": tower.tower_ss_damping_1,
                    "ss_2": tower.tower_ss_damping_2,
                },
                "mode_coeffs": {
                    "fa_mode_1": tower.fa_mode_1_coeffs,
                    "fa_mode_2": tower.fa_mode_2_coeffs,
                    "ss_mode_1": tower.ss_mode_1_coeffs,
                    "ss_mode_2": tower.ss_mode_2_coeffs,
                },
            }

    # Load blade
    blade_data = None
    if tm.blade_id:
        b_result = await db.execute(select(Blade).where(Blade.id == tm.blade_id))
        blade = b_result.scalar_one_or_none()
        if blade:
            blade_data = {
                "structural_stations": blade.structural_stations or [],
                "blade_length": blade.blade_length,
                "damping": {
                    "flap": blade.blade_flap_damping,
                    "edge": blade.blade_edge_damping,
                },
                "mode_coeffs": {
                    "flap_mode_1": blade.flap_mode_1_coeffs,
                    "flap_mode_2": blade.flap_mode_2_coeffs,
                    "edge_mode_1": blade.edge_mode_1_coeffs,
                },
            }

    # Build turbine model dict
    tm_dict = {
        "hub_mass": tm.hub_mass,
        "nacelle_mass": tm.nacelle_mass,
        "hub_inertia": tm.hub_inertia,
        "nacelle_inertia": tm.nacelle_inertia,
        "generator_inertia": tm.generator_inertia,
        "gearbox_ratio": tm.gearbox_ratio,
        "rotor_speed_rated": tm.rotor_speed_rated,
        "overhang": tm.overhang,
        "shaft_tilt": tm.shaft_tilt,
        "precone": tm.precone,
        "num_blades": 3,
        "substructure_config": tm.substructure_config,
    }

    return tower_data, blade_data, tm_dict


# ---------------------------------------------------------------------------
# endpoints
# ---------------------------------------------------------------------------
@router.post("/natural-frequencies", response_model=FrequencyResponse)
async def compute_frequencies(
    project_id: str,
    body: FrequencyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute natural frequencies for a given structural stage."""
    await _verify_project(project_id, current_user.org_id, db)
    tower_data, blade_data, tm_dict = await _load_turbine_context(
        body.turbine_model_id, project_id, db
    )

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        compute_combined_frequencies,
        tower_data,
        blade_data,
        tm_dict,
        body.stage,
        10,
    )

    return FrequencyResponse(
        stage=result["stage"],
        stage_label=result["stage_label"],
        rotor_speed_rpm=body.rotor_speed_rpm,
        frequencies_hz=result["frequencies_hz"],
        mode_descriptions=result["mode_descriptions"],
        component_info={"tower": tower_data is not None, "blade": blade_data is not None},
    )


@router.post("/campbell", response_model=CampbellResponse)
async def compute_campbell(
    project_id: str,
    body: CampbellRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute Campbell diagram data (frequency vs rotor speed)."""
    await _verify_project(project_id, current_user.org_id, db)
    tower_data, blade_data, tm_dict = await _load_turbine_context(
        body.turbine_model_id, project_id, db
    )

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        compute_campbell_diagram,
        tower_data,
        blade_data,
        tm_dict,
        body.rpm_min,
        body.rpm_max,
        body.rpm_steps,
        body.n_modes,
    )

    return CampbellResponse(**result)


@router.post("/multi-stage", response_model=MultiStageResponse)
async def compute_multi_stage(
    project_id: str,
    body: MultiStageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute frequencies at multiple project stages for side-by-side comparison."""
    await _verify_project(project_id, current_user.org_id, db)
    tower_data, blade_data, tm_dict = await _load_turbine_context(
        body.turbine_model_id, project_id, db
    )

    loop = asyncio.get_running_loop()
    stages = []
    for stage in body.stages:
        result = await loop.run_in_executor(
            None,
            compute_combined_frequencies,
            tower_data,
            blade_data,
            tm_dict,
            stage,
            10,
        )
        stages.append(result)

    return MultiStageResponse(stages=stages)
