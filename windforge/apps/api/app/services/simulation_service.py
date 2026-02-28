"""Background service for OpenFAST simulation pipeline.

Four phases per case:
  1. Generate input files (.fst, .dat, .inp)
  2. Run TurbSim to produce .bts wind field
  3. Run OpenFAST to produce .out time-series
  4. Parse .out and persist results to DB
"""

import asyncio
import logging
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import async_session_factory
from app.models.components import Tower, Blade, Controller, TurbineModel as TurbineModelORM
from app.models.project import Project as ProjectORM
from app.models.simulation import (
    CaseStatus,
    ResultsExtreme,
    ResultsStatistics,
    Simulation,
    SimulationCase,
    SimulationStatus,
)
from app.openfast.file_generator import (
    OpenFASTFileGenerator,
    TurbineModel as TurbineModelDC,
    SimulationCase as SimulationCaseDC,
    Project as ProjectDC,
)
from app.openfast.output_reader import OutputReader
from app.openfast.servodyn_generator import ServoDynConfig, DISCONConfig
from app.openfast.elastodyn_generator import (
    ElastoDynBladeConfig,
    ElastoDynTowerConfig,
    BladeStation,
    TowerStation,
)
from app.openfast.aerodyn_generator import AeroDynBladeConfig, AeroBladeStation
from app.routers.websocket import publish_event

logger = logging.getLogger("windforge.simulation_service")


# ---------------------------------------------------------------------------
# Binary availability check
# ---------------------------------------------------------------------------

def _check_binaries() -> dict[str, bool]:
    """Check whether TurbSim and OpenFAST binaries are on PATH."""
    return {
        "turbsim": shutil.which(settings.TURBSIM_EXE) is not None,
        "openfast": shutil.which(settings.OPENFAST_EXE) is not None,
    }


# ---------------------------------------------------------------------------
# Subprocess runners (sync — called via run_in_executor)
# ---------------------------------------------------------------------------

def _run_turbsim_sync(inp_file: str, turbsim_exe: str) -> Path | None:
    """Run TurbSim as a subprocess. Returns path to .bts or None."""
    inp_path = Path(inp_file)
    proc = subprocess.run(
        [turbsim_exe, str(inp_path)],
        cwd=str(inp_path.parent),
        capture_output=True,
        text=True,
        timeout=1800,  # 30-minute timeout per case
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"TurbSim failed (exit {proc.returncode}): "
            f"{proc.stderr[-500:] if proc.stderr else proc.stdout[-500:]}"
        )
    # Look for the .bts output file
    bts_file = inp_path.with_suffix(".bts")
    if bts_file.is_file():
        return bts_file
    # Search for any .bts in the directory
    bts_files = list(inp_path.parent.glob("*.bts"))
    return max(bts_files, key=lambda p: p.stat().st_mtime) if bts_files else None


def _run_openfast_sync(fst_file: str, openfast_exe: str) -> Path | None:
    """Run OpenFAST as a subprocess. Returns path to .out/.outb or None."""
    fst_path = Path(fst_file)
    proc = subprocess.run(
        [openfast_exe, str(fst_path)],
        cwd=str(fst_path.parent),
        capture_output=True,
        text=True,
        timeout=3600,  # 1-hour timeout
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"OpenFAST failed (exit {proc.returncode}): "
            f"{proc.stderr[-500:] if proc.stderr else proc.stdout[-500:]}"
        )
    stem = fst_path.stem
    for suffix in (".outb", ".out"):
        candidate = fst_path.parent / (stem + suffix)
        if candidate.is_file():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Results persistence helpers
# ---------------------------------------------------------------------------

async def _persist_case_results(
    output_file: Path,
    sim: Simulation,
    case: SimulationCase,
    db,
) -> None:
    """Parse .out file and create a ResultsStatistics record."""
    reader = OutputReader()
    output_data = reader.load(output_file)

    channel_statistics: dict = {}
    for idx, (name, unit) in enumerate(
        zip(output_data.channel_names, output_data.channel_units)
    ):
        if name.upper() == "TIME":
            continue
        col = output_data.data[:, idx]
        channel_statistics[name] = {
            "min": float(np.nanmin(col)),
            "max": float(np.nanmax(col)),
            "mean": float(np.nanmean(col)),
            "std": float(np.nanstd(col)),
            "abs_max": float(np.nanmax(np.abs(col))),
            "unit": unit,
        }

    stats = ResultsStatistics(
        simulation_id=sim.id,
        simulation_case_id=case.id,
        dlc_number=case.dlc_number,
        wind_speed=case.wind_speed,
        channel_statistics=channel_statistics,
    )
    db.add(stats)
    await db.flush()


async def _persist_aggregated_results(sim: Simulation, db) -> None:
    """Aggregate extreme loads across all cases and store."""
    result = await db.execute(
        select(ResultsStatistics).where(ResultsStatistics.simulation_id == sim.id)
    )
    all_stats = result.scalars().all()
    if not all_stats:
        return

    extreme_loads: dict = {}
    for stat in all_stats:
        if not stat.channel_statistics:
            continue
        for channel, vals in stat.channel_statistics.items():
            if channel not in extreme_loads:
                extreme_loads[channel] = {
                    "max": vals["max"],
                    "min": vals["min"],
                    "safety_factor": 1.35,
                    "design_value": vals["max"] * 1.35,
                }
            else:
                ex = extreme_loads[channel]
                ex["max"] = max(ex["max"], vals["max"])
                ex["min"] = min(ex["min"], vals["min"])
                ex["design_value"] = ex["max"] * ex["safety_factor"]

    if extreme_loads:
        db.add(ResultsExtreme(simulation_id=sim.id, extreme_loads=extreme_loads))
        await db.flush()


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

# Keep backward compat alias
async def run_file_generation(simulation_id: str, project_id: str) -> None:
    """Alias for run_simulation_pipeline (backward compat)."""
    return await run_simulation_pipeline(simulation_id, project_id)


async def run_simulation_pipeline(simulation_id: str, project_id: str) -> None:
    """Background task: generate files → run TurbSim → run OpenFAST → persist results.

    Runs as an asyncio task kicked off by start_simulation().
    Uses its own DB session (not the request session).
    """
    start_time = time.monotonic()

    async with async_session_factory() as db:
        try:
            # 1. Load simulation with cases
            result = await db.execute(
                select(Simulation)
                .where(Simulation.id == simulation_id)
                .options(selectinload(Simulation.cases))
            )
            sim = result.scalar_one_or_none()
            if sim is None:
                logger.error("Simulation %s not found", simulation_id)
                return

            # 2. Load turbine model with tower, blade, controller
            tm_result = await db.execute(
                select(TurbineModelORM).where(TurbineModelORM.id == sim.turbine_model_id)
            )
            tm = tm_result.scalar_one_or_none()
            if tm is None:
                sim.status = SimulationStatus.FAILED
                await db.commit()
                await publish_event(simulation_id, {
                    "type": "simulation_error",
                    "error": "Turbine model not found",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                return

            # Load related components
            tower = None
            if tm.tower_id:
                t_result = await db.execute(select(Tower).where(Tower.id == tm.tower_id))
                tower = t_result.scalar_one_or_none()

            blade = None
            if tm.blade_id:
                b_result = await db.execute(select(Blade).where(Blade.id == tm.blade_id))
                blade = b_result.scalar_one_or_none()

            controller = None
            if tm.controller_id:
                c_result = await db.execute(select(Controller).where(Controller.id == tm.controller_id))
                controller = c_result.scalar_one_or_none()

            # Load project
            proj_result = await db.execute(select(ProjectORM).where(ProjectORM.id == project_id))
            project = proj_result.scalar_one_or_none()
            if project is None:
                sim.status = SimulationStatus.FAILED
                await db.commit()
                return

            # 3. Build file generator dataclasses
            turbine_dc = _build_turbine_model_dc(tm, tower, blade, controller, project)
            project_dc = _build_project_dc(project)

            # 4. Create output directory
            base_dir = Path(settings.PROJECTS_DIR) / str(project_id) / "simulations" / str(simulation_id) / "cases"
            base_dir.mkdir(parents=True, exist_ok=True)

            # Check binary availability
            binaries = _check_binaries()
            can_execute = binaries["turbsim"] and binaries["openfast"]
            logger.info(
                "Binary check: turbsim=%s openfast=%s → execute=%s",
                binaries["turbsim"], binaries["openfast"], can_execute,
            )

            # 5. Generate files for each case
            generator = OpenFASTFileGenerator()
            total = len(sim.cases)
            completed = 0
            failed = 0
            case_dirs: dict[str, tuple[SimulationCase, Path, str]] = {}  # case_id → (case, dir, fst_name)

            # Publish start event
            await publish_event(simulation_id, {
                "type": "generation_started",
                "total_cases": total,
                "execute_mode": can_execute,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # ── Phase 1: Generate input files ──────────────────────────
            for case in sim.cases:
                try:
                    case_dir_name = (
                        f"DLC{case.dlc_number.replace('.', '')}"
                        f"_v{case.wind_speed:05.1f}"
                        f"_s{case.seed_number}"
                        f"_y{int(case.yaw_misalignment)}"
                    )
                    case_dir = base_dir / case_dir_name
                    case_dir.mkdir(parents=True, exist_ok=True)

                    case_dc = SimulationCaseDC(
                        case_id=case_dir_name,
                        dlc_number=case.dlc_number,
                        wind_speed=case.wind_speed,
                        seed_number=case.seed_number,
                        yaw_misalignment=case.yaw_misalignment,
                        simulation_time=630.0,
                        dt=0.005,
                        wind_type=3,
                    )

                    case.status = CaseStatus.RUNNING
                    case.started_at = datetime.now(timezone.utc)
                    await db.flush()

                    await publish_event(simulation_id, {
                        "type": "case_progress",
                        "case_id": str(case.id),
                        "status": "generating",
                        "message": (
                            f"Generating files for DLC {case.dlc_number} "
                            f"@ {case.wind_speed} m/s (seed {case.seed_number})"
                        ),
                        "progress": int((completed / max(total, 1)) * 100),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                    files = generator.generate_all(turbine_dc, case_dc, project_dc)

                    file_list = []
                    fst_name = None
                    for filename, content in files.items():
                        filepath = case_dir / filename
                        filepath.parent.mkdir(parents=True, exist_ok=True)
                        filepath.write_text(content, encoding="utf-8")
                        file_list.append(filename)
                        if filename.endswith(".fst"):
                            fst_name = filename

                    case.input_files = {"directory": str(case_dir), "files": file_list}
                    case_dirs[str(case.id)] = (case, case_dir, fst_name or f"{case_dir_name}.fst")
                    await db.flush()

                    await publish_event(simulation_id, {
                        "type": "case_complete",
                        "case_id": str(case.id),
                        "phase": "file_generation",
                        "files_generated": file_list,
                        "directory": str(case_dir),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                except Exception as e:
                    logger.exception("Failed to generate files for case %s", case.id)
                    case.status = CaseStatus.FAILED
                    case.error_message = str(e)
                    case.completed_at = datetime.now(timezone.utc)
                    failed += 1
                    await db.flush()

                    await publish_event(simulation_id, {
                        "type": "case_error",
                        "case_id": str(case.id),
                        "error": str(e),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                await asyncio.sleep(0.01)

            # If no binaries available, complete in generate-only mode
            if not can_execute:
                elapsed = time.monotonic() - start_time
                # Mark file-generation-only cases as completed
                for cid, (case, _, _) in case_dirs.items():
                    case.status = CaseStatus.COMPLETED
                    case.progress_percent = 100.0
                    case.completed_at = datetime.now(timezone.utc)
                    completed += 1
                sim.completed_cases = completed
                sim.failed_cases = failed
                sim.status = SimulationStatus.COMPLETED
                sim.completed_at = datetime.now(timezone.utc)
                await db.commit()

                await publish_event(simulation_id, {
                    "type": "simulation_complete",
                    "simulation_id": str(simulation_id),
                    "mode": "generate_only",
                    "completed": completed,
                    "failed": failed,
                    "total": total,
                    "elapsed_seconds": round(elapsed, 2),
                    "message": (
                        "Input files generated. TurbSim/OpenFAST binaries not found "
                        "on PATH — skipping execution. Install OpenFAST to run simulations."
                    ),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                logger.info(
                    "Simulation %s: generate-only mode (%d cases, %.1fs)",
                    simulation_id, completed, elapsed,
                )
                return

            # ── Phase 2 & 3: TurbSim + OpenFAST execution ─────────────
            sim.status = SimulationStatus.GENERATING_WIND
            await db.flush()
            loop = asyncio.get_running_loop()

            for cid, (case, case_dir, fst_name) in case_dirs.items():
                if case.status == CaseStatus.FAILED:
                    continue  # skip cases that failed file generation

                try:
                    # Phase 2: TurbSim
                    turbsim_inp_files = list(case_dir.glob("*_TurbSim.inp")) + list(case_dir.glob("*TurbSim*.inp"))
                    if turbsim_inp_files:
                        inp_file = turbsim_inp_files[0]
                        await publish_event(simulation_id, {
                            "type": "case_progress",
                            "case_id": cid,
                            "status": "generating_wind",
                            "message": f"Running TurbSim for DLC {case.dlc_number} @ {case.wind_speed} m/s...",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })

                        bts_path = await loop.run_in_executor(
                            None, _run_turbsim_sync, str(inp_file), settings.TURBSIM_EXE
                        )

                        if bts_path:
                            case.wind_field_path = str(bts_path)
                            await publish_event(simulation_id, {
                                "type": "case_progress",
                                "case_id": cid,
                                "status": "turbsim_complete",
                                "message": f"TurbSim complete: {bts_path.name}",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            })

                    # Phase 3: OpenFAST
                    sim.status = SimulationStatus.RUNNING
                    case.status = CaseStatus.RUNNING
                    await db.flush()

                    await publish_event(simulation_id, {
                        "type": "case_progress",
                        "case_id": cid,
                        "status": "running_openfast",
                        "message": f"Running OpenFAST for DLC {case.dlc_number} @ {case.wind_speed} m/s...",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                    out_path = await loop.run_in_executor(
                        None, _run_openfast_sync, str(case_dir / fst_name), settings.OPENFAST_EXE
                    )

                    if out_path and out_path.is_file():
                        # Phase 4: Parse results
                        await publish_event(simulation_id, {
                            "type": "case_progress",
                            "case_id": cid,
                            "status": "parsing_results",
                            "message": f"Parsing results for DLC {case.dlc_number} @ {case.wind_speed} m/s...",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })

                        await _persist_case_results(out_path, sim, case, db)

                        case.input_files = {
                            **(case.input_files or {}),
                            "output_file": str(out_path),
                        }
                        case.status = CaseStatus.COMPLETED
                        case.progress_percent = 100.0
                        case.completed_at = datetime.now(timezone.utc)
                        case.wall_time_seconds = (case.completed_at - case.started_at).total_seconds()
                        completed += 1
                    else:
                        case.status = CaseStatus.FAILED
                        case.error_message = "OpenFAST produced no output file"
                        case.completed_at = datetime.now(timezone.utc)
                        failed += 1

                    await db.flush()

                    await publish_event(simulation_id, {
                        "type": "case_complete",
                        "case_id": cid,
                        "phase": "execution",
                        "output_file": str(out_path) if out_path else None,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                except Exception as e:
                    logger.exception("Execution failed for case %s", case.id)
                    case.status = CaseStatus.FAILED
                    case.error_message = str(e)
                    case.completed_at = datetime.now(timezone.utc)
                    failed += 1
                    await db.flush()

                    await publish_event(simulation_id, {
                        "type": "case_error",
                        "case_id": cid,
                        "error": str(e),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                await asyncio.sleep(0.01)

            # ── Phase 5: Aggregate results ─────────────────────────────
            if completed > 0:
                try:
                    await _persist_aggregated_results(sim, db)
                except Exception as e:
                    logger.warning("Failed to aggregate results: %s", e)

            # 6. Update simulation status
            elapsed = time.monotonic() - start_time
            sim.completed_cases = completed
            sim.failed_cases = failed
            sim.completed_at = datetime.now(timezone.utc)

            if failed == total:
                sim.status = SimulationStatus.FAILED
            else:
                sim.status = SimulationStatus.COMPLETED

            await db.commit()

            await publish_event(simulation_id, {
                "type": "simulation_complete",
                "simulation_id": str(simulation_id),
                "mode": "full_execution",
                "completed": completed,
                "failed": failed,
                "total": total,
                "elapsed_seconds": round(elapsed, 2),
                "output_directory": str(base_dir),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            logger.info(
                "Simulation %s pipeline complete: %d/%d cases in %.1fs",
                simulation_id, completed, total, elapsed,
            )

        except Exception as e:
            logger.exception("Fatal error in simulation pipeline for %s", simulation_id)
            try:
                sim.status = SimulationStatus.FAILED
                await db.commit()
            except Exception:
                pass

            await publish_event(simulation_id, {
                "type": "simulation_error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })


def _build_turbine_model_dc(
    tm: TurbineModelORM,
    tower: Tower | None,
    blade: Blade | None,
    controller: Controller | None,
    project: ProjectORM,
) -> TurbineModelDC:
    """Convert ORM models to the file generator TurbineModel dataclass."""

    # Build tower config
    tower_config = None
    if tower and tower.stations:
        stations = []
        for s in tower.stations:
            # Tower station JSON keys: {frac, mass_den, fa_stiff, ss_stiff, ...}
            # ElastoDyn TowerStation fields: ht_fract, t_mass_den, tw_fa_stif, tw_ss_stif
            stations.append(TowerStation(
                ht_fract=s.get("frac", s.get("height_fraction", 0)),
                t_mass_den=s.get("mass_den", s.get("mass_density_kg_m", 0)),
                tw_fa_stif=s.get("fa_stiff", s.get("FA_stiffness_Nm2", 0)),
                tw_ss_stif=s.get("ss_stiff", s.get("SS_stiffness_Nm2", 0)),
            ))
        # ElastoDynTowerConfig fields: twr_fa_dmp1, twr_ss_dmp1, twr_fa_dmp2, twr_ss_dmp2
        # Mode shapes: fa_mode_1, fa_mode_2, ss_mode_1, ss_mode_2 (5 coefficients each)
        tower_config = ElastoDynTowerConfig(
            n_tw_inp_st=len(stations),
            twr_fa_dmp1=tower.tower_fa_damping_1,
            twr_ss_dmp1=tower.tower_ss_damping_1,
            twr_fa_dmp2=tower.tower_fa_damping_2,
            twr_ss_dmp2=tower.tower_ss_damping_2,
            stations=stations,
            fa_mode_1=_mode_coeffs(tower.fa_mode_1_coeffs, [0.7004, 2.1963, -5.6202, 6.2275, -2.5040]),
            fa_mode_2=_mode_coeffs(tower.fa_mode_2_coeffs, [-26.0840, 73.8440, -78.5640, 34.1800, -2.3760]),
            ss_mode_1=_mode_coeffs(tower.ss_mode_1_coeffs, [0.6360, 2.2124, -5.5836, 6.2433, -2.5081]),
            ss_mode_2=_mode_coeffs(tower.ss_mode_2_coeffs, [-26.5340, 75.0040, -79.3660, 34.2560, -2.3600]),
        )

    # Build blade config
    blade_config = None
    aerodyn_blade_config = None
    if blade and blade.structural_stations:
        # Blade structural station JSON keys: {frac, pitch_axis, struct_twist, mass_den, flap_stiff, edge_stiff}
        # ElastoDyn BladeStation fields: bl_fract, pitch_ax, strc_twist, b_mass_den, flp_stff, edg_stff
        blade_stations = []
        for s in blade.structural_stations:
            blade_stations.append(BladeStation(
                bl_fract=s.get("frac", s.get("fraction", 0)),
                pitch_ax=s.get("pitch_axis", 0.5),
                strc_twist=s.get("struct_twist", s.get("structural_twist_deg", 0)),
                b_mass_den=s.get("mass_den", s.get("mass_density_kg_m", 0)),
                flp_stff=s.get("flap_stiff", s.get("flapwise_stiffness_Nm2", 0)),
                edg_stff=s.get("edge_stiff", s.get("edgewise_stiffness_Nm2", 0)),
            ))
        # ElastoDynBladeConfig fields: n_bl_inp_st, bld_flex_l, bld_fl_dmp_1/2, bld_ed_dmp_1
        # Mode shapes: flp_mode_1, flp_mode_2, edg_mode_1 (5 coefficients each)
        blade_config = ElastoDynBladeConfig(
            n_bl_inp_st=len(blade_stations),
            bld_flex_l=blade.blade_length,
            bld_fl_dmp_1=blade.blade_flap_damping,
            bld_fl_dmp_2=blade.blade_flap_damping,
            bld_ed_dmp_1=blade.blade_edge_damping,
            stations=blade_stations,
            flp_mode_1=_mode_coeffs(blade.flap_mode_1_coeffs, [0.0622, 1.7254, -3.2452, 4.7131, -2.2555]),
            flp_mode_2=_mode_coeffs(blade.flap_mode_2_coeffs, [-0.5809, 1.2067, -15.5349, 29.7347, -13.8255]),
            edg_mode_1=_mode_coeffs(blade.edge_mode_1_coeffs, [0.3627, 2.5337, -3.5772, 2.3760, -0.6952]),
        )

        # Build AeroDyn blade config from aero stations
        if blade.aero_stations:
            # AeroDyn AeroBladeStation fields: bl_spn, bl_crv_ac, bl_swp_ac, bl_crv_ang,
            #                                  bl_twist, bl_chord, bl_af_id
            # Blade aero station JSON keys: {frac, chord, aero_twist, airfoil_id, aero_center}
            #
            # airfoil_id in DB is a name string (e.g. "Cylinder1", "NACA64_A17").
            # bl_af_id in the file generator is a 1-based integer index into the
            # AFNames list. Build a unique ordered list and map names to indices.
            unique_airfoils: list[str] = []
            airfoil_index: dict[str, int] = {}
            for s in blade.aero_stations:
                af_name = s.get("airfoil_id", "Cylinder")
                if af_name not in airfoil_index:
                    unique_airfoils.append(af_name)
                    airfoil_index[af_name] = len(unique_airfoils)  # 1-based

            aero_stations = []
            for s in blade.aero_stations:
                frac = s.get("frac", s.get("fraction", 0))
                af_name = s.get("airfoil_id", "Cylinder")
                aero_stations.append(AeroBladeStation(
                    bl_spn=frac * blade.blade_length,
                    bl_crv_ac=0.0,
                    bl_swp_ac=0.0,
                    bl_crv_ang=0.0,
                    bl_twist=s.get("aero_twist", s.get("aero_twist_deg", 0)),
                    bl_chord=s.get("chord", s.get("chord_m", 0)),
                    bl_af_id=airfoil_index[af_name],
                ))
            aerodyn_blade_config = AeroDynBladeConfig(
                num_bl_nds=len(aero_stations),
                stations=aero_stations,
            )

    # Build ServoDyn config
    servodyn_config = None
    discon_config = None
    if controller:
        # Resolve DLL path: prefer absolute ROSCO_LIB_PATH over bare filename
        dll_filename = settings.ROSCO_LIB_PATH or controller.dll_filename or "libdiscon.dylib"
        dll_procname = controller.dll_procname or "DISCON"
        servodyn_config = ServoDynConfig(
            pc_mode=controller.pcmode,
            vs_contrl=controller.vscontrl,
            dll_file_name=dll_filename,
            dll_proc_name=dll_procname,
        )
        discon_config = DISCONConfig(
            we_blade_radius=tm.overhang or 63.0,
            we_gear_ratio=tm.gearbox_ratio or 97.0,
            vs_rated_gen_pwr=(project.rated_power or 5000.0) * 1000.0,
        )

    # Build HydroDyn config for offshore
    hydrodyn_config = None
    subdyn_config = None
    moordyn_config = None
    platform_type = project.platform_type or "onshore"
    water_depth = project.water_depth or 0.0

    if platform_type != "onshore" and tm.hydrodyn_config:
        from app.openfast.hydrodyn_generator import HydroDynConfig as HDConfig
        hd = tm.hydrodyn_config
        hydrodyn_config = HDConfig(
            wave_mod=hd.get("wave_mod", 2),
            wave_hs=hd.get("wave_hs", 1.5),
            wave_tp=hd.get("wave_tp", 8.0),
            wtr_dpth=hd.get("wtr_dpth", water_depth),
        )

    if platform_type in ("monopile", "jacket") and tm.substructure_config:
        from app.openfast.subdyn_generator import SubDynConfig as SDConfig
        sub = tm.substructure_config
        subdyn_config = SDConfig(
            joints=sub.get("joints", []),
            members=sub.get("members", []),
        )

    if platform_type in ("spar", "semi_submersible", "tlp") and tm.moordyn_config:
        from app.openfast.moordyn_generator import MoorDynConfig as MDConfig
        moor = tm.moordyn_config
        moordyn_config = MDConfig(
            line_types=moor.get("line_types", []),
            points=moor.get("points", []),
            mooring_lines=moor.get("mooring_lines", moor.get("lines", [])),
        )

    return TurbineModelDC(
        name=tm.name,
        num_blades=project.num_blades or 3,
        tip_radius=(project.rotor_diameter or 126.0) / 2.0,
        hub_radius=1.5,
        hub_height=project.hub_height or 90.0,
        tower_height=tower.tower_height if tower else 87.6,
        tower_base_height=tower.tower_base_height if tower else 10.0,
        rated_power_kw=project.rated_power or 5000.0,
        rated_wind_speed=project.rated_speed or 11.4,
        rated_rotor_speed=tm.rotor_speed_rated or 12.1,
        cut_in_wind_speed=project.cut_in_speed or 3.0,
        cut_out_wind_speed=project.cut_out_speed or 25.0,
        gearbox_ratio=tm.gearbox_ratio or 97.0,
        rotor_overhang=tm.overhang or -5.0191,
        shaft_tilt=tm.shaft_tilt or -5.0,
        precone=tm.precone or -2.5,
        tower_config=tower_config,
        blade_config=blade_config,
        aerodyn_blade_config=aerodyn_blade_config,
        servodyn_config=servodyn_config,
        discon_config=discon_config,
        platform_type=platform_type,
        water_depth=water_depth,
        hydrodyn_config=hydrodyn_config,
        subdyn_config=subdyn_config,
        moordyn_config=moordyn_config,
    )


def _build_project_dc(project: ProjectORM) -> ProjectDC:
    """Convert ORM Project to file generator Project dataclass."""
    # Map wind class letter to number
    turbine_class_map = {"I": 1, "II": 2, "III": 3}
    wc = project.wind_class or "I"
    tc = turbine_class_map.get(wc[0] if wc else "I", 1)
    turb_class = project.turbulence_class or "B"

    return ProjectDC(
        name=project.name,
        iec_class=f"{wc}{turb_class}",
        turbine_class=tc,
        turbulence_class=turb_class,
    )


def _mode_coeffs(db_coeffs: list[float] | None, defaults: list[float]) -> list[float]:
    """Return mode shape coefficients, trimmed or padded to 5 entries.

    The ORM stores 6 polynomial coefficients (ARRAY(Float)) but
    ElastoDyn mode shape configs expect exactly 5 (x^2 through x^6).
    If the DB array has 6 values we take the first 5; if fewer we pad
    with zeros; if None we return the provided defaults.
    """
    if db_coeffs is None:
        return defaults
    coeffs = list(db_coeffs)
    if len(coeffs) >= 5:
        return coeffs[:5]
    return coeffs + [0.0] * (5 - len(coeffs))
