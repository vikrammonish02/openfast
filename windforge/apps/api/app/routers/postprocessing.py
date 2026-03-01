"""Post-processing endpoints -- project-scoped.

All computation delegates to openfast_toolbox validated functions
via the postprocessing_service module.

IEC loads analysis endpoints process real OpenFAST simulation
output files using validated ExtremeLoadExtractor, DELCalculator,
and StatisticsCalculator modules.
"""

import asyncio
import logging
from functools import partial
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.project import Project
from app.models.simulation import (
    CaseStatus,
    DLCDefinition,
    Simulation,
    SimulationCase,
    SimulationStatus,
)
from app.models.user import User
from app.schemas.postprocessing import (
    DampingRequest,
    DampingResponse,
    DelFatigueRequest,
    DelFatigueResponse,
    ExtremeValueRequest,
    ExtremeValueResponse,
    IECCaseInfo,
    IECCasesGrouped,
    IECChannelListResponse,
    IECGumbelRequest,
    IECGumbelResponse,
    IECLoadsRequest,
    IECLoadsResponse,
    IECSimulationInfo,
    SpectralRequest,
    SpectralResponse,
    StatisticsRequest,
    StatisticsResponse,
)
from app.services.postprocessing_service import (
    compute_damping,
    compute_del_fatigue,
    compute_extreme_value,
    compute_iec_gumbel,
    compute_spectral,
    compute_statistics,
    get_available_channels,
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


@router.post("/extreme-value", response_model=ExtremeValueResponse)
async def extreme_value(
    project_id: str,
    body: ExtremeValueRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Extreme value extrapolation using Gumbel (EV1) distribution.

    Based on NREL/CP-500-25787 and NREL/TP-500-34421.
    Generates N simulations, extracts block maxima, fits Gumbel,
    and extrapolates to target return periods with 95% confidence bounds.
    """
    await _verify_project(project_id, current_user.org_id, db)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        partial(
            compute_extreme_value,
            signal_type=body.signal_type,
            amplitude=body.amplitude,
            frequency=body.frequency,
            noise_std=body.noise_std,
            mean_load=body.mean_load,
            duration=body.duration,
            dt=body.dt,
            n_simulations=body.n_simulations,
            block_size=body.block_size,
            threshold_sigma=body.threshold_sigma,
            return_periods=body.return_periods,
        ),
    )
    return ExtremeValueResponse(**result)


# ===========================================================================
# IEC 61400-1 Loads Analysis (Real Simulation Data)
# ===========================================================================

async def _resolve_case_output_path(case: SimulationCase) -> Path | None:
    """Resolve the output file path for a completed simulation case."""
    output_path: Path | None = None

    # Try explicit output_file key first
    if case.input_files and "output_file" in case.input_files:
        output_path = Path(case.input_files["output_file"])

    # Fall back: search the case directory for .out / .outb files
    if output_path is None or not output_path.is_file():
        case_dir: Path | None = None
        if case.input_files and "directory" in case.input_files:
            case_dir = Path(case.input_files["directory"])
        if case_dir is None or not case_dir.is_dir():
            return None
        candidates = list(case_dir.glob("*.outb")) + list(case_dir.glob("*.out"))
        if not candidates:
            return None
        output_path = candidates[0]

    if not output_path.is_file():
        return None

    return output_path


async def _build_case_configs(
    cases: list[SimulationCase],
    dlc_definition: DLCDefinition | None,
) -> list:
    """Build CaseConfig objects from SimulationCase records."""
    from app.services.iec_loads_service import CaseConfig

    # Build a DLC -> safety factor map from the definition
    dlc_sf_map: dict[str, float] = {}
    if dlc_definition and dlc_definition.dlc_cases:
        for dlc_spec in dlc_definition.dlc_cases:
            dlc_num = dlc_spec.get("dlc_number", "")
            sf = dlc_spec.get("partial_safety_factor", 1.35)
            if dlc_num:
                dlc_sf_map[dlc_num] = sf

    configs: list[CaseConfig] = []
    for case in cases:
        if case.status != CaseStatus.COMPLETED:
            continue

        output_path = await _resolve_case_output_path(case)
        if output_path is None:
            continue

        # Safety factor: from DLC definition or default
        sf = dlc_sf_map.get(case.dlc_number, 1.35)

        configs.append(CaseConfig(
            case_id=case.id,
            output_path=str(output_path),
            dlc_number=case.dlc_number,
            wind_speed=case.wind_speed,
            seed=case.seed_number,
            yaw_misalignment=case.yaw_misalignment,
            safety_factor=sf,
            probability_weight=case.probability_weight or 1.0,
            analysis_type=case.analysis_type or "ultimate",
        ))

    return configs


@router.get("/iec-loads/simulations", response_model=list[IECSimulationInfo])
async def list_simulations_for_iec(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all simulations with completed cases available for IEC loads analysis."""
    await _verify_project(project_id, current_user.org_id, db)

    result = await db.execute(
        select(Simulation)
        .where(Simulation.project_id == project_id)
        .order_by(Simulation.created_at.desc())
    )
    simulations = result.scalars().all()

    items: list[IECSimulationInfo] = []
    for sim in simulations:
        if sim.completed_cases == 0:
            continue  # Skip simulations with no completed cases

        # Collect unique DLC numbers from cases
        dlc_numbers: set[str] = set()
        for case in sim.cases:
            if case.status == CaseStatus.COMPLETED:
                dlc_numbers.add(case.dlc_number)

        items.append(IECSimulationInfo(
            id=sim.id,
            name=sim.name,
            status=sim.status.value,
            total_cases=sim.total_cases,
            completed_cases=sim.completed_cases,
            failed_cases=sim.failed_cases,
            dlc_numbers=sorted(dlc_numbers),
            created_at=sim.created_at.isoformat() if sim.created_at else "",
        ))

    return items


@router.get(
    "/iec-loads/simulations/{simulation_id}/cases",
    response_model=list[IECCasesGrouped],
)
async def get_iec_cases_grouped(
    project_id: str,
    simulation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get completed cases for a simulation, grouped by DLC number."""
    await _verify_project(project_id, current_user.org_id, db)

    result = await db.execute(
        select(Simulation).where(
            Simulation.id == simulation_id,
            Simulation.project_id == project_id,
        )
    )
    sim = result.scalar_one_or_none()
    if sim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")

    # Group cases by DLC
    dlc_groups: dict[str, list[IECCaseInfo]] = {}
    for case in sim.cases:
        dlc = case.dlc_number
        if dlc not in dlc_groups:
            dlc_groups[dlc] = []
        dlc_groups[dlc].append(IECCaseInfo(
            case_id=case.id,
            dlc_number=case.dlc_number,
            wind_speed=case.wind_speed,
            seed_number=case.seed_number,
            yaw_misalignment=case.yaw_misalignment,
            analysis_type=case.analysis_type or "ultimate",
            safety_factor=1.35,  # Default; overridden in analysis
            probability_weight=case.probability_weight or 1.0,
            status=case.status.value,
        ))

    grouped: list[IECCasesGrouped] = []
    for dlc_num in sorted(dlc_groups.keys()):
        cases_list = dlc_groups[dlc_num]
        grouped.append(IECCasesGrouped(
            dlc_number=dlc_num,
            cases=cases_list,
            total_cases=len(cases_list),
            completed_cases=sum(1 for c in cases_list if c.status == "completed"),
        ))

    return grouped


@router.post("/iec-loads", response_model=IECLoadsResponse)
async def iec_loads_analysis(
    project_id: str,
    body: IECLoadsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run IEC 61400-1 loads analysis on real OpenFAST simulation outputs.

    Processes selected simulation cases through validated ExtremeLoadExtractor,
    DELCalculator, and StatisticsCalculator to produce IEC-compliant loads tables.
    """
    await _verify_project(project_id, current_user.org_id, db)

    # Load simulation with cases
    result = await db.execute(
        select(Simulation).where(
            Simulation.id == body.simulation_id,
            Simulation.project_id == project_id,
        )
    )
    sim = result.scalar_one_or_none()
    if sim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")

    # Load DLC definition for safety factors
    dlc_def = None
    if sim.dlc_definition_id:
        dlc_result = await db.execute(
            select(DLCDefinition).where(DLCDefinition.id == sim.dlc_definition_id)
        )
        dlc_def = dlc_result.scalar_one_or_none()

    # Filter cases
    cases = list(sim.cases)
    if body.case_ids:
        cases = [c for c in cases if c.id in body.case_ids]
    if body.dlc_filter:
        cases = [c for c in cases if c.dlc_number in body.dlc_filter]

    # Build case configs
    case_configs = await _build_case_configs(cases, dlc_def)

    if not case_configs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No completed cases with output files found for the selected criteria",
        )

    # Run analysis in executor (CPU-bound)
    from app.services.iec_loads_service import run_iec_loads_analysis

    loop = asyncio.get_running_loop()
    iec_result = await loop.run_in_executor(
        None,
        partial(
            run_iec_loads_analysis,
            case_configs=case_configs,
            simulation_id=sim.id,
            simulation_name=sim.name,
            channels=body.channels,
            t_start=body.t_start,
            wohler_exponents=body.wohler_exponents,
            n_equivalent=body.n_equivalent,
            consequence_factor=body.consequence_factor,
        ),
    )

    # Convert dataclass result to Pydantic response
    return IECLoadsResponse(
        simulation_id=iec_result.simulation_id,
        simulation_name=iec_result.simulation_name,
        n_cases_analyzed=iec_result.n_cases_analyzed,
        channels_analyzed=iec_result.channels_analyzed,
        extreme_loads=[
            {
                "channel": r.channel, "unit": r.unit,
                "max_characteristic": r.max_characteristic, "max_design": r.max_design,
                "max_dlc": r.max_dlc, "max_vhub": r.max_vhub, "max_time": r.max_time,
                "max_case_id": r.max_case_id,
                "min_characteristic": r.min_characteristic, "min_design": r.min_design,
                "min_dlc": r.min_dlc, "min_vhub": r.min_vhub, "min_time": r.min_time,
                "min_case_id": r.min_case_id,
                "safety_factor_max": r.safety_factor_max,
                "safety_factor_min": r.safety_factor_min,
            }
            for r in iec_result.extreme_loads
        ],
        concurrent_loads=[
            {
                "governing_channel": cl.governing_channel,
                "extreme_type": cl.extreme_type,
                "timestep_values": cl.timestep_values,
            }
            for cl in iec_result.concurrent_loads
        ],
        del_table=[
            {
                "channel": d.channel, "unit": d.unit,
                "del_values": d.del_values, "n_equivalent": d.n_equivalent,
            }
            for d in iec_result.del_table
        ],
        statistics_table=[
            {
                "channel": s.channel, "unit": s.unit,
                "mean": s.mean, "std": s.std,
                "min_val": s.min_val, "max_val": s.max_val,
                "abs_max": s.abs_max, "n_cases": s.n_cases,
            }
            for s in iec_result.statistics_table
        ],
        case_summary=[
            {
                "case_id": cs.case_id, "dlc_number": cs.dlc_number,
                "wind_speed": cs.wind_speed, "seed_number": cs.seed_number,
                "yaw_misalignment": cs.yaw_misalignment,
                "analysis_type": cs.analysis_type,
                "safety_factor": cs.safety_factor,
                "probability_weight": cs.probability_weight,
            }
            for cs in iec_result.case_summary
        ],
    )


@router.post("/iec-loads/excel")
async def iec_loads_excel(
    project_id: str,
    body: IECLoadsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run IEC loads analysis and return an Excel (.xlsx) download.

    Produces a multi-sheet workbook with:
      - Summary (project, turbine, DLC info)
      - Extreme Loads (with concurrent loads)
      - Fatigue DEL
      - Statistics
      - DLC Cases
    """
    project = await _verify_project(project_id, current_user.org_id, db)

    # Load simulation
    result = await db.execute(
        select(Simulation).where(
            Simulation.id == body.simulation_id,
            Simulation.project_id == project_id,
        )
    )
    sim = result.scalar_one_or_none()
    if sim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")

    # Load DLC definition
    dlc_def = None
    if sim.dlc_definition_id:
        dlc_result = await db.execute(
            select(DLCDefinition).where(DLCDefinition.id == sim.dlc_definition_id)
        )
        dlc_def = dlc_result.scalar_one_or_none()

    # Filter cases
    cases = list(sim.cases)
    if body.case_ids:
        cases = [c for c in cases if c.id in body.case_ids]
    if body.dlc_filter:
        cases = [c for c in cases if c.dlc_number in body.dlc_filter]

    case_configs = await _build_case_configs(cases, dlc_def)
    if not case_configs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No completed cases with output files found",
        )

    from app.services.iec_loads_service import generate_iec_loads_excel, run_iec_loads_analysis

    loop = asyncio.get_running_loop()

    # Run analysis
    iec_result = await loop.run_in_executor(
        None,
        partial(
            run_iec_loads_analysis,
            case_configs=case_configs,
            simulation_id=sim.id,
            simulation_name=sim.name,
            channels=body.channels,
            t_start=body.t_start,
            wohler_exponents=body.wohler_exponents,
            n_equivalent=body.n_equivalent,
            consequence_factor=body.consequence_factor,
        ),
    )

    # Build turbine info from project
    turbine_info = {
        "rotor_diameter": getattr(project, "rotor_diameter", ""),
        "hub_height": getattr(project, "hub_height", ""),
        "rated_power": getattr(project, "rated_power", ""),
        "num_blades": getattr(project, "num_blades", ""),
        "cut_in_speed": getattr(project, "cut_in_speed", ""),
        "cut_out_speed": getattr(project, "cut_out_speed", ""),
        "wind_class": getattr(project, "wind_class", ""),
        "turbulence_class": getattr(project, "turbulence_class", ""),
    }

    # Generate Excel
    excel_bytes = await loop.run_in_executor(
        None,
        partial(
            generate_iec_loads_excel,
            result=iec_result,
            project_name=project.name,
            turbine_info=turbine_info,
        ),
    )

    import io

    filename = f"IEC_Loads_{project.name.replace(' ', '_')}_{sim.name.replace(' ', '_')}.xlsx"
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ===========================================================================
# IEC Gumbel Extreme Value Extrapolation (Real Simulation Data)
# ===========================================================================

@router.get(
    "/iec-gumbel/simulations/{simulation_id}/channels",
    response_model=IECChannelListResponse,
)
async def get_iec_gumbel_channels(
    project_id: str,
    simulation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get available channels for Gumbel analysis from a simulation's output files."""
    await _verify_project(project_id, current_user.org_id, db)

    result = await db.execute(
        select(Simulation).where(
            Simulation.id == simulation_id,
            Simulation.project_id == project_id,
        )
    )
    sim = result.scalar_one_or_none()
    if sim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")

    # Load DLC definition for safety factors
    dlc_def = None
    if sim.dlc_definition_id:
        dlc_result = await db.execute(
            select(DLCDefinition).where(DLCDefinition.id == sim.dlc_definition_id)
        )
        dlc_def = dlc_result.scalar_one_or_none()

    cases = [c for c in sim.cases if c.status == CaseStatus.COMPLETED]
    case_configs = await _build_case_configs(cases, dlc_def)

    if not case_configs:
        return IECChannelListResponse(simulation_id=simulation_id, channels=[])

    loop = asyncio.get_running_loop()
    channels = await loop.run_in_executor(
        None,
        partial(get_available_channels, case_configs=case_configs),
    )

    return IECChannelListResponse(simulation_id=simulation_id, channels=channels)


@router.post("/iec-gumbel", response_model=IECGumbelResponse)
async def iec_gumbel_analysis(
    project_id: str,
    body: IECGumbelRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run Gumbel (EV1) extreme value extrapolation on real simulation outputs.

    Reads block maxima from selected DLC cases for a chosen channel,
    fits Gumbel distribution, and extrapolates to target return periods
    with 95% confidence bounds. Follows NREL/CP-500-25787 methodology.
    """
    await _verify_project(project_id, current_user.org_id, db)

    # Load simulation
    result = await db.execute(
        select(Simulation).where(
            Simulation.id == body.simulation_id,
            Simulation.project_id == project_id,
        )
    )
    sim = result.scalar_one_or_none()
    if sim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")

    # Load DLC definition
    dlc_def = None
    if sim.dlc_definition_id:
        dlc_result = await db.execute(
            select(DLCDefinition).where(DLCDefinition.id == sim.dlc_definition_id)
        )
        dlc_def = dlc_result.scalar_one_or_none()

    # Filter cases
    cases = list(sim.cases)
    if body.case_ids:
        cases = [c for c in cases if c.id in body.case_ids]
    if body.dlc_filter:
        cases = [c for c in cases if c.dlc_number in body.dlc_filter]

    case_configs = await _build_case_configs(cases, dlc_def)

    if not case_configs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No completed cases with output files found for the selected criteria",
        )

    loop = asyncio.get_running_loop()
    gumbel_result = await loop.run_in_executor(
        None,
        partial(
            compute_iec_gumbel,
            case_configs=case_configs,
            channel=body.channel,
            t_start=body.t_start,
            block_size=body.block_size,
            return_periods=body.return_periods,
        ),
    )

    return IECGumbelResponse(**gumbel_result)
