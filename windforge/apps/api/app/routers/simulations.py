"""Simulation endpoints: CRUD, execution control, results retrieval."""

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.openfast.output_reader import OutputReader
from app.models.project import Project
from app.models.simulation import (
    CaseStatus,
    DLCDefinition,
    ResultsDEL,
    ResultsExtreme,
    ResultsStatistics,
    Simulation,
    SimulationCase,
    SimulationStatus,
)
from app.models.user import User
from app.services.simulation_service import run_simulation_pipeline
from app.schemas.simulation import (
    DLCDefinitionCreate,
    DLCDefinitionResponse,
    DLCDefinitionUpdate,
    ResultsDELResponse,
    ResultsExtremeResponse,
    ResultsStatisticsResponse,
    SimulationCaseResponse,
    SimulationCreate,
    SimulationResponse,
    SimulationWithProgress,
)

router = APIRouter(prefix="/projects/{project_id}/simulations", tags=["simulations"])


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


async def _get_simulation_or_404(
    sim_id: str, project_id: str, db: AsyncSession
) -> Simulation:
    result = await db.execute(
        select(Simulation).where(
            Simulation.id == sim_id, Simulation.project_id == project_id
        )
    )
    sim = result.scalar_one_or_none()
    if sim is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found"
        )
    return sim


def _compute_progress(sim: Simulation) -> SimulationWithProgress:
    """Build an extended response with progress metrics."""
    total = max(sim.total_cases, 1)
    completed = sim.completed_cases + sim.failed_cases
    pct = (completed / total) * 100.0

    est_remaining: float | None = None
    if sim.started_at and completed > 0 and pct < 100.0:
        elapsed = (datetime.now(timezone.utc) - sim.started_at).total_seconds()
        per_case = elapsed / completed
        remaining_cases = total - completed
        est_remaining = per_case * remaining_cases

    return SimulationWithProgress(
        id=sim.id,
        project_id=sim.project_id,
        dlc_definition_id=sim.dlc_definition_id,
        turbine_model_id=sim.turbine_model_id,
        name=sim.name,
        status=sim.status.value,
        total_cases=sim.total_cases,
        completed_cases=sim.completed_cases,
        failed_cases=sim.failed_cases,
        agent_id=sim.agent_id,
        started_at=sim.started_at,
        completed_at=sim.completed_at,
        created_at=sim.created_at,
        progress_percent=round(pct, 2),
        estimated_remaining_seconds=round(est_remaining, 1) if est_remaining else None,
    )


def _get(spec, key: str, default=None):
    """Get a value from a dict or pydantic model (handles both formats)."""
    if isinstance(spec, dict):
        return spec.get(key, default)
    return getattr(spec, key, default)


def _lookup_metocean(
    metocean: dict | None,
    wind_speeds: list[float],
    sea_state: str,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Interpolate metocean table to get wave Hs/Tp/gamma for each wind speed.

    Uses numpy interpolation from the metocean condition table.
    Sea-state selects which column set to use (NSS, SSS, ESS).
    """
    if not metocean:
        return [None] * len(wind_speeds), [None] * len(wind_speeds), [None] * len(wind_speeds)

    met_ws = metocean.get("wind_speeds", [])
    if not met_ws:
        return [None] * len(wind_speeds), [None] * len(wind_speeds), [None] * len(wind_speeds)

    # Select column set by sea state
    ss_map = {
        "NSS": ("wave_hs_nss", "wave_tp_nss"),
        "SSS": ("wave_hs_sss", "wave_tp_sss"),
        "ESS": ("wave_hs_ess", "wave_tp_ess"),
        "fatigue": ("wave_hs_nss", "wave_tp_nss"),
        "1yr": ("wave_hs_sss", "wave_tp_sss"),
        "50yr": ("wave_hs_ess", "wave_tp_ess"),
    }
    hs_key, tp_key = ss_map.get(sea_state, ("wave_hs_nss", "wave_tp_nss"))
    met_hs = metocean.get(hs_key) or metocean.get("wave_hs_nss")
    met_tp = metocean.get(tp_key) or metocean.get("wave_tp_nss")
    met_gamma = metocean.get("wave_gamma")

    if not met_hs or not met_tp:
        return [None] * len(wind_speeds), [None] * len(wind_speeds), [None] * len(wind_speeds)

    hs_out = list(np.interp(wind_speeds, met_ws, met_hs))
    tp_out = list(np.interp(wind_speeds, met_ws, met_tp))
    gamma_out = list(np.interp(wind_speeds, met_ws, met_gamma)) if met_gamma else [None] * len(wind_speeds)

    return hs_out, tp_out, gamma_out


def _lookup_initial_condition(
    initial_conditions: dict | None,
    wind_speed: float,
    key: str,
) -> float | None:
    """Interpolate initial condition from lookup table."""
    if not initial_conditions:
        return None
    ws_table = initial_conditions.get("wind_speed")
    val_table = initial_conditions.get(key)
    if not ws_table or not val_table or len(ws_table) != len(val_table):
        return None
    return float(np.interp(wind_speed, ws_table, val_table))


def _expand_dlc_cases(dlc_def: DLCDefinition) -> list[dict]:
    """Expand the DLC case matrix into individual simulation cases.

    WEIS-style grouped variable expansion:
      Group 0 (constants): wave_dir, shutdown_time — same for all cases
      Group 1 (correlated): wind_speed + wave_hs + wave_tp vary TOGETHER
      Group 2 (Cartesian): seeds × yaw × azimuth × wave_seeds
    """
    metocean = dlc_def.metocean_conditions
    cases: list[dict] = []

    for spec in (dlc_def.dlc_cases or []):
        dlc_number = _get(spec, "dlc_number", "1.1")
        wind_speeds = _get(spec, "wind_speeds", [])
        seeds = _get(spec, "seeds", 6)
        yaw_misalignments = _get(spec, "yaw_misalignments", [0.0])

        # WEIS fields with defaults
        sea_state = _get(spec, "sea_state", "NSS")
        wave_hs_override = _get(spec, "wave_hs")
        wave_tp_override = _get(spec, "wave_tp")
        wave_gamma_override = _get(spec, "wave_gamma")
        wave_dir = _get(spec, "wave_dir", 0.0)
        wave_seed_start = _get(spec, "wave_seed_start", 1000)
        n_wave_seeds = _get(spec, "n_wave_seeds", 1)
        iec_wind_type = _get(spec, "iec_wind_type", "NTM")
        wind_profile_type = _get(spec, "wind_profile_type", "IEC")
        n_azimuth = _get(spec, "n_azimuth", 1)
        azimuth_init = _get(spec, "azimuth_init", 0.0)
        shutdown_time = _get(spec, "shutdown_time")
        probability_weight = _get(spec, "probability_weight", 1.0)
        analysis_type = _get(spec, "analysis_type", "ultimate")
        initial_conditions = _get(spec, "initial_conditions")

        # Group 1: build correlated wind-wave pairs
        if wave_hs_override and len(wave_hs_override) == len(wind_speeds):
            wave_hs_list = wave_hs_override
            wave_tp_list = wave_tp_override or [None] * len(wind_speeds)
            wave_gamma_list = wave_gamma_override or [None] * len(wind_speeds)
        else:
            # Auto-populate from metocean table
            wave_hs_list, wave_tp_list, wave_gamma_list = _lookup_metocean(
                metocean, wind_speeds, sea_state
            )

        # Group 2: independent sweep dimensions
        azimuth_step = 360.0 / n_azimuth if n_azimuth > 1 else 360.0
        azimuths = [azimuth_init + i * azimuth_step for i in range(n_azimuth)]
        wave_seeds = [wave_seed_start + i for i in range(n_wave_seeds)]

        # Expand: Group1 (correlated) × Group2 (Cartesian product)
        for i, ws in enumerate(wind_speeds):
            hs_val = wave_hs_list[i] if i < len(wave_hs_list) else None
            tp_val = wave_tp_list[i] if i < len(wave_tp_list) else None
            gm_val = wave_gamma_list[i] if i < len(wave_gamma_list) else None

            # Interpolate initial conditions if provided
            init_rpm = _lookup_initial_condition(initial_conditions, ws, "rotor_speed")
            init_pitch = _lookup_initial_condition(initial_conditions, ws, "blade_pitch")

            for seed in range(1, seeds + 1):
                for yaw in yaw_misalignments:
                    for az in azimuths:
                        for wseed in wave_seeds:
                            cases.append(
                                {
                                    "dlc_number": dlc_number,
                                    "wind_speed": ws,
                                    "seed_number": seed,
                                    "yaw_misalignment": yaw,
                                    "wave_hs": hs_val,
                                    "wave_tp": tp_val,
                                    "wave_dir": wave_dir,
                                    "wave_seed": wseed,
                                    "wave_gamma": gm_val,
                                    "iec_wind_type": iec_wind_type,
                                    "wind_profile_type": wind_profile_type,
                                    "azimuth_deg": az,
                                    "probability_weight": probability_weight,
                                    "initial_rotor_speed": init_rpm,
                                    "initial_blade_pitch": init_pitch,
                                    "shutdown_time": shutdown_time,
                                    "analysis_type": analysis_type,
                                }
                            )
    return cases


# ---------------------------------------------------------------------------
# DLC Definition endpoints (nested under simulations for convenience)
# ---------------------------------------------------------------------------
dlc_router = APIRouter(prefix="/projects/{project_id}/dlc-definitions", tags=["dlc"])


@dlc_router.post("", response_model=DLCDefinitionResponse, status_code=status.HTTP_201_CREATED)
async def create_dlc_definition(
    project_id: str,
    body: DLCDefinitionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project(project_id, current_user.org_id, db)

    # Serialize nested schemas
    dlc_cases_data = None
    if body.dlc_cases:
        dlc_cases_data = [c.model_dump() for c in body.dlc_cases]

    turbsim_data = body.turbsim_params.model_dump() if body.turbsim_params else None
    metocean_data = body.metocean_conditions.model_dump() if body.metocean_conditions else None

    # Count total cases (including wave seeds and azimuth)
    total = 0
    for spec in (body.dlc_cases or []):
        total += (
            len(spec.wind_speeds)
            * spec.seeds
            * len(spec.yaw_misalignments)
            * spec.n_wave_seeds
            * spec.n_azimuth
        )

    dlc = DLCDefinition(
        project_id=project_id,
        turbine_model_id=body.turbine_model_id,
        name=body.name,
        dlc_cases=dlc_cases_data,
        turbsim_params=turbsim_data,
        metocean_conditions=metocean_data,
        total_case_count=total,
    )
    db.add(dlc)
    await db.flush()
    await db.refresh(dlc)
    return DLCDefinitionResponse.model_validate(dlc)


@dlc_router.get("", response_model=list[DLCDefinitionResponse])
async def list_dlc_definitions(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project(project_id, current_user.org_id, db)
    result = await db.execute(
        select(DLCDefinition)
        .where(DLCDefinition.project_id == project_id)
        .order_by(DLCDefinition.created_at.desc())
    )
    return [DLCDefinitionResponse.model_validate(d) for d in result.scalars().all()]


@dlc_router.get("/{dlc_id}", response_model=DLCDefinitionResponse)
async def get_dlc_definition(
    project_id: str,
    dlc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project(project_id, current_user.org_id, db)
    result = await db.execute(
        select(DLCDefinition).where(
            DLCDefinition.id == dlc_id, DLCDefinition.project_id == project_id
        )
    )
    dlc = result.scalar_one_or_none()
    if dlc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DLC definition not found")
    return DLCDefinitionResponse.model_validate(dlc)


@dlc_router.put("/{dlc_id}", response_model=DLCDefinitionResponse)
async def update_dlc_definition(
    project_id: str,
    dlc_id: str,
    body: DLCDefinitionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project(project_id, current_user.org_id, db)
    result = await db.execute(
        select(DLCDefinition).where(
            DLCDefinition.id == dlc_id, DLCDefinition.project_id == project_id
        )
    )
    dlc = result.scalar_one_or_none()
    if dlc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DLC definition not found")

    update_data = body.model_dump(exclude_unset=True)
    if "dlc_cases" in update_data and update_data["dlc_cases"] is not None:
        update_data["dlc_cases"] = [
            c.model_dump() if hasattr(c, "model_dump") else c for c in update_data["dlc_cases"]
        ]
        # Recount total cases (including wave seeds and azimuth)
        total = 0
        for spec in body.dlc_cases:
            total += (
                len(spec.wind_speeds)
                * spec.seeds
                * len(spec.yaw_misalignments)
                * spec.n_wave_seeds
                * spec.n_azimuth
            )
        dlc.total_case_count = total

    if "turbsim_params" in update_data and update_data["turbsim_params"] is not None:
        update_data["turbsim_params"] = (
            update_data["turbsim_params"].model_dump()
            if hasattr(update_data["turbsim_params"], "model_dump")
            else update_data["turbsim_params"]
        )

    if "metocean_conditions" in update_data and update_data["metocean_conditions"] is not None:
        update_data["metocean_conditions"] = (
            update_data["metocean_conditions"].model_dump()
            if hasattr(update_data["metocean_conditions"], "model_dump")
            else update_data["metocean_conditions"]
        )

    for field, value in update_data.items():
        setattr(dlc, field, value)

    await db.flush()
    await db.refresh(dlc)
    return DLCDefinitionResponse.model_validate(dlc)


@dlc_router.delete("/{dlc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dlc_definition(
    project_id: str,
    dlc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project(project_id, current_user.org_id, db)
    result = await db.execute(
        select(DLCDefinition).where(
            DLCDefinition.id == dlc_id, DLCDefinition.project_id == project_id
        )
    )
    dlc = result.scalar_one_or_none()
    if dlc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DLC definition not found")
    await db.delete(dlc)
    await db.flush()


# ---------------------------------------------------------------------------
# Simulation endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[SimulationResponse])
async def list_simulations(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project(project_id, current_user.org_id, db)
    result = await db.execute(
        select(Simulation)
        .where(Simulation.project_id == project_id)
        .order_by(Simulation.created_at.desc())
    )
    return [SimulationResponse.model_validate(s) for s in result.scalars().all()]


@router.post("", response_model=SimulationWithProgress, status_code=status.HTTP_201_CREATED)
async def create_simulation(
    project_id: str,
    body: SimulationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a simulation batch with individual cases expanded from the DLC definition."""
    await _verify_project(project_id, current_user.org_id, db)

    # Fetch the DLC definition
    result = await db.execute(
        select(DLCDefinition).where(
            DLCDefinition.id == body.dlc_definition_id,
            DLCDefinition.project_id == project_id,
        )
    )
    dlc_def = result.scalar_one_or_none()
    if dlc_def is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="DLC definition not found"
        )

    # Expand cases
    expanded = _expand_dlc_cases(dlc_def)

    sim = Simulation(
        project_id=project_id,
        dlc_definition_id=body.dlc_definition_id,
        turbine_model_id=body.turbine_model_id,
        name=body.name,
        total_cases=len(expanded),
    )
    db.add(sim)
    await db.flush()

    # Bulk-insert simulation cases
    for case_data in expanded:
        case = SimulationCase(simulation_id=sim.id, **case_data)
        db.add(case)

    await db.flush()
    await db.refresh(sim)
    return _compute_progress(sim)


@router.get("/{simulation_id}", response_model=SimulationWithProgress)
async def get_simulation(
    project_id: str,
    simulation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project(project_id, current_user.org_id, db)
    sim = await _get_simulation_or_404(simulation_id, project_id, db)
    return _compute_progress(sim)


@router.post("/{simulation_id}/start", response_model=SimulationWithProgress)
async def start_simulation(
    project_id: str,
    simulation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a simulation as ready to run (agent picks it up)."""
    await _verify_project(project_id, current_user.org_id, db)
    sim = await _get_simulation_or_404(simulation_id, project_id, db)

    if sim.status != SimulationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot start simulation in '{sim.status.value}' state",
        )

    sim.status = SimulationStatus.GENERATING_WIND
    sim.started_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(sim)

    # Kick off background file generation (runs in its own DB session)
    asyncio.create_task(run_simulation_pipeline(sim.id, project_id))

    return _compute_progress(sim)


@router.post("/{simulation_id}/cancel", response_model=SimulationWithProgress)
async def cancel_simulation(
    project_id: str,
    simulation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running or pending simulation."""
    await _verify_project(project_id, current_user.org_id, db)
    sim = await _get_simulation_or_404(simulation_id, project_id, db)

    if sim.status in (SimulationStatus.COMPLETED, SimulationStatus.CANCELLED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel simulation in '{sim.status.value}' state",
        )

    sim.status = SimulationStatus.CANCELLED
    sim.completed_at = datetime.now(timezone.utc)

    # Cancel any pending / running cases
    result = await db.execute(
        select(SimulationCase).where(
            SimulationCase.simulation_id == sim.id,
            SimulationCase.status.in_([CaseStatus.PENDING, CaseStatus.RUNNING, CaseStatus.GENERATING_WIND]),
        )
    )
    for case in result.scalars().all():
        case.status = CaseStatus.CANCELLED

    await db.flush()
    await db.refresh(sim)
    return _compute_progress(sim)


@router.get("/{simulation_id}/cases", response_model=list[SimulationCaseResponse])
async def list_cases(
    project_id: str,
    simulation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project(project_id, current_user.org_id, db)
    await _get_simulation_or_404(simulation_id, project_id, db)

    result = await db.execute(
        select(SimulationCase)
        .where(SimulationCase.simulation_id == simulation_id)
        .order_by(SimulationCase.wind_speed, SimulationCase.seed_number)
    )
    return [SimulationCaseResponse.model_validate(c) for c in result.scalars().all()]


@router.get(
    "/{simulation_id}/results/statistics",
    response_model=list[ResultsStatisticsResponse],
)
async def get_statistics(
    project_id: str,
    simulation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project(project_id, current_user.org_id, db)
    await _get_simulation_or_404(simulation_id, project_id, db)

    result = await db.execute(
        select(ResultsStatistics)
        .where(ResultsStatistics.simulation_id == simulation_id)
        .order_by(ResultsStatistics.wind_speed)
    )
    return [ResultsStatisticsResponse.model_validate(r) for r in result.scalars().all()]


@router.get("/{simulation_id}/results/del", response_model=list[ResultsDELResponse])
async def get_del_results(
    project_id: str,
    simulation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project(project_id, current_user.org_id, db)
    await _get_simulation_or_404(simulation_id, project_id, db)

    result = await db.execute(
        select(ResultsDEL).where(ResultsDEL.simulation_id == simulation_id)
    )
    return [ResultsDELResponse.model_validate(r) for r in result.scalars().all()]


@router.get(
    "/{simulation_id}/results/extreme",
    response_model=list[ResultsExtremeResponse],
)
async def get_extreme_results(
    project_id: str,
    simulation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project(project_id, current_user.org_id, db)
    await _get_simulation_or_404(simulation_id, project_id, db)

    result = await db.execute(
        select(ResultsExtreme).where(ResultsExtreme.simulation_id == simulation_id)
    )
    return [ResultsExtremeResponse.model_validate(r) for r in result.scalars().all()]


# ---------------------------------------------------------------------------
# Time series / channel endpoints
# ---------------------------------------------------------------------------

async def _get_case_output_path(
    simulation_id: str,
    case_id: str,
    project_id: str,
    db: AsyncSession,
) -> tuple[SimulationCase, Path]:
    """Look up a completed SimulationCase and resolve its output file path.

    Returns the case object and the validated output file path.
    Raises HTTPException on any failure.
    """
    result = await db.execute(
        select(SimulationCase).where(
            SimulationCase.id == case_id,
            SimulationCase.simulation_id == simulation_id,
        )
    )
    case = result.scalar_one_or_none()
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Simulation case not found"
        )

    if case.status != CaseStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Case is not completed (status: {case.status.value})",
        )

    # Try explicit output_file key first
    output_path: Path | None = None
    if case.input_files and "output_file" in case.input_files:
        output_path = Path(case.input_files["output_file"])

    # Fall back: search the case directory for .out / .outb files
    if output_path is None or not output_path.is_file():
        case_dir: Path | None = None
        if case.input_files and "directory" in case.input_files:
            case_dir = Path(case.input_files["directory"])
        if case_dir is None or not case_dir.is_dir():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case output directory not found",
            )
        candidates = list(case_dir.glob("*.outb")) + list(case_dir.glob("*.out"))
        if not candidates:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No output file (.out/.outb) found for this case",
            )
        output_path = candidates[0]

    # Security: ensure resolved path stays within PROJECTS_DIR
    try:
        resolved = output_path.resolve()
        projects_resolved = Path(settings.PROJECTS_DIR).resolve()
        if not str(resolved).startswith(str(projects_resolved)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )
    except (OSError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid output path"
        )

    if not resolved.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Output file not found on disk",
        )

    return case, resolved


@router.get("/{simulation_id}/cases/{case_id}/channels")
async def get_case_channels(
    project_id: str,
    simulation_id: str,
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the list of available output channels for a completed case."""
    await _verify_project(project_id, current_user.org_id, db)
    await _get_simulation_or_404(simulation_id, project_id, db)
    _case, output_path = await _get_case_output_path(
        simulation_id, case_id, project_id, db
    )

    try:
        reader = OutputReader()
        output_data = reader.load(output_path)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read output file: {exc}",
        )

    channels = [
        {"name": name, "unit": unit}
        for name, unit in zip(output_data.channel_names, output_data.channel_units)
    ]
    return {"channels": channels}


@router.get("/{simulation_id}/cases/{case_id}/timeseries")
async def get_case_timeseries(
    project_id: str,
    simulation_id: str,
    case_id: str,
    channels: str = Query(
        ..., description="Comma-separated list of channel names to retrieve"
    ),
    downsample: int = Query(
        1, ge=1, description="Take every Nth sample (1 = no downsampling)"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return time series data for selected output channels of a completed case."""
    await _verify_project(project_id, current_user.org_id, db)
    await _get_simulation_or_404(simulation_id, project_id, db)
    case, output_path = await _get_case_output_path(
        simulation_id, case_id, project_id, db
    )

    try:
        reader = OutputReader()
        output_data = reader.load(output_path)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read output file: {exc}",
        )

    requested = [ch.strip() for ch in channels.split(",") if ch.strip()]
    if not requested:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No channels specified",
        )

    # Build a case-insensitive lookup for channel names -> index
    name_to_idx: dict[str, int] = {
        name.upper(): idx for idx, name in enumerate(output_data.channel_names)
    }
    unit_lookup: dict[str, str] = {
        name.upper(): unit
        for name, unit in zip(output_data.channel_names, output_data.channel_units)
    }

    # Validate all requested channels exist
    missing = [ch for ch in requested if ch.upper() not in name_to_idx]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown channels: {', '.join(missing)}",
        )

    # Apply downsampling
    time_arr = output_data.time[::downsample]
    dt = output_data.dt * downsample

    channels_payload: dict = {}
    for ch in requested:
        idx = name_to_idx[ch.upper()]
        values = output_data.data[::downsample, idx]
        # Find the original-cased name for the unit lookup
        unit = unit_lookup[ch.upper()]
        channels_payload[ch] = {
            "unit": unit,
            "values": np.where(np.isfinite(values), values, None).tolist(),
        }

    return {
        "case_id": str(case_id),
        "time": np.where(np.isfinite(time_arr), time_arr, None).tolist(),
        "dt": dt,
        "num_timesteps": len(time_arr),
        "channels": channels_payload,
        "available_channels": output_data.channel_names,
    }
