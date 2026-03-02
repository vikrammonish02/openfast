"""Simulation, DLC, case, and results schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Metocean conditions (WEIS-style correlated wind-wave table)
# ---------------------------------------------------------------------------
class MetoceanConditions(BaseModel):
    """Correlated wind-wave conditions table (like WEIS metocean_conditions).

    Each list is indexed by wind speed bin.  Wave heights and periods vary
    by sea-state severity: NSS (Normal), SSS (Severe), ESS (Extreme).
    """

    wind_speeds: list[float] = Field(..., description="Wind speed bins (m/s)")
    wave_hs_nss: list[float] = Field(..., description="NSS significant wave height (m)")
    wave_tp_nss: list[float] = Field(..., description="NSS peak period (s)")
    wave_hs_sss: list[float] | None = Field(default=None, description="SSS Hs (m)")
    wave_tp_sss: list[float] | None = Field(default=None, description="SSS Tp (s)")
    wave_hs_ess: list[float] | None = Field(default=None, description="ESS Hs (m)")
    wave_tp_ess: list[float] | None = Field(default=None, description="ESS Tp (s)")
    wave_gamma: list[float] | None = Field(
        default=None, description="JONSWAP peak shape parameter per wind speed"
    )
    water_depth: float = Field(default=30.0, ge=0, description="Water depth (m)")
    current_speed: float = Field(default=0.0, ge=0, description="Current speed (m/s)")


# ---------------------------------------------------------------------------
# DLC case specification (nested inside DLCDefinition)
# ---------------------------------------------------------------------------
class DLCCaseSpec(BaseModel):
    """Specification for a single DLC within a definition.

    Supports both simple (original) and rich (IEC + WEIS-enhanced) configs.
    The new fields all have defaults, so existing saved definitions remain
    fully compatible.
    """

    dlc_number: str = Field(..., description="e.g. '1.1', '1.3', '6.1', '2.1c'")
    wind_speeds: list[float] = Field(..., description="List of wind speeds (m/s)")
    seeds: int = Field(default=6, ge=1, description="Number of random seeds")
    yaw_misalignments: list[float] = Field(
        default=[0.0], description="Yaw misalignment angles (deg)"
    )

    # --- IEC-enhanced fields (all optional with sensible defaults) ---
    wind_condition: str = Field(
        default="NTM",
        description="Wind model: NTM, ETM, EWM, EOG, ECD, EDC, EWS, NWP",
    )
    partial_safety_factor: float = Field(
        default=1.35, ge=0.0, description="Partial safety factor gamma_f"
    )
    analysis_type: str = Field(
        default="ultimate",
        description="'ultimate' or 'fatigue'",
    )
    simulation_length: float = Field(
        default=600.0, gt=0, description="Simulation length in seconds"
    )
    init_length: float = Field(
        default=200.0, ge=0, description="Initialization / discard length in seconds"
    )
    description: str = Field(
        default="", description="Custom label or description for the DLC"
    )
    is_custom: bool = Field(
        default=False, description="True for user-added sub-DLC variants"
    )

    # --- WEIS-enhanced fields (wave, wind type, azimuth, etc.) ---
    sea_state: str = Field(
        default="NSS",
        description="Sea state type: NSS, SSS, ESS, fatigue, 1yr, 50yr",
    )
    wave_hs: list[float] | None = Field(
        default=None,
        description="Override: Hs per wind speed (correlated with wind_speeds)",
    )
    wave_tp: list[float] | None = Field(
        default=None,
        description="Override: Tp per wind speed (correlated with wind_speeds)",
    )
    wave_gamma: list[float] | None = Field(
        default=None,
        description="Override: JONSWAP gamma per wind speed",
    )
    wave_dir: float = Field(default=0.0, description="Wave direction (deg)")
    wave_seed_start: int = Field(
        default=1000,
        description="Starting wave seed (independent from wind seeds)",
    )
    n_wave_seeds: int = Field(
        default=1, ge=1, description="Number of wave seeds per case"
    )
    iec_wind_type: str = Field(
        default="NTM",
        description="TurbSim IEC wind type: NTM, 1ETM, 1EWM1, 1EWM50, etc.",
    )
    wind_profile_type: str = Field(
        default="IEC",
        description="Wind profile: IEC, LOG, PL, JET",
    )
    n_azimuth: int = Field(
        default=1, ge=1,
        description="Number of azimuth positions for transient DLCs (1 = no sweep)",
    )
    azimuth_init: float = Field(
        default=0.0, description="Starting azimuth angle (deg)"
    )
    shutdown_time: float | None = Field(
        default=None,
        description="Shutdown trigger time in seconds (DLC 5.1)",
    )
    probability_weight: float = Field(
        default=1.0, ge=0.0,
        description="Occurrence probability weight for fatigue DLCs",
    )
    initial_conditions: dict | None = Field(
        default=None,
        description=(
            "Lookup table: {rotor_speed: [...], blade_pitch: [...], wind_speed: [...]}"
        ),
    )


class TurbSimParamsSchema(BaseModel):
    """TurbSim configuration parameters."""

    turbulence_model: str = Field(default="IECKAI", description="e.g. IECKAI, IECVKM, GP_LLJ")
    iec_standard: str = Field(default="1-ED3")
    iec_turbc: str = Field(default="B", description="IEC turbulence category")
    grid_height: float = Field(default=150.0, gt=0)
    grid_width: float = Field(default=150.0, gt=0)
    num_grid_z: int = Field(default=25, ge=3)
    num_grid_y: int = Field(default=25, ge=3)
    time_step: float = Field(default=0.05, gt=0)
    analysis_time: float = Field(default=660.0, gt=0)
    ref_height: float = Field(default=90.0, gt=0)


# ---------------------------------------------------------------------------
# DLC Definition
# ---------------------------------------------------------------------------
class DLCDefinitionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    turbine_model_id: str
    dlc_cases: list[DLCCaseSpec] | None = None
    turbsim_params: TurbSimParamsSchema | None = None
    metocean_conditions: MetoceanConditions | None = None


class DLCDefinitionUpdate(BaseModel):
    name: str | None = None
    dlc_cases: list[DLCCaseSpec] | None = None
    turbsim_params: TurbSimParamsSchema | None = None
    metocean_conditions: MetoceanConditions | None = None


class DLCDefinitionResponse(BaseModel):
    id: str
    project_id: str
    turbine_model_id: str
    name: str
    dlc_cases: list[DLCCaseSpec] | None = None
    turbsim_params: TurbSimParamsSchema | None = None
    metocean_conditions: MetoceanConditions | None = None
    total_case_count: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------
class SimulationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    dlc_definition_id: str
    turbine_model_id: str


class SimulationResponse(BaseModel):
    id: str
    project_id: str
    dlc_definition_id: str
    turbine_model_id: str
    name: str
    status: str
    total_cases: int
    completed_cases: int
    failed_cases: int
    agent_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SimulationWithProgress(SimulationResponse):
    """Extended response with computed progress fields."""

    progress_percent: float = 0.0
    estimated_remaining_seconds: float | None = None


# ---------------------------------------------------------------------------
# SimulationCase
# ---------------------------------------------------------------------------
class SimulationCaseResponse(BaseModel):
    id: str
    simulation_id: str
    dlc_number: str
    wind_speed: float
    seed_number: int
    yaw_misalignment: float
    # WEIS-enhanced fields
    wave_hs: float | None = None
    wave_tp: float | None = None
    wave_dir: float | None = None
    wave_seed: int | None = None
    wave_gamma: float | None = None
    iec_wind_type: str | None = None
    wind_profile_type: str | None = None
    azimuth_deg: float | None = None
    probability_weight: float | None = None
    initial_rotor_speed: float | None = None
    initial_blade_pitch: float | None = None
    shutdown_time: float | None = None
    analysis_type: str | None = None
    # Standard fields
    wind_field_path: str | None = None
    input_files: dict | None = None
    status: str
    progress_percent: float
    current_time: float
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    wall_time_seconds: float | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
class ChannelStatistic(BaseModel):
    """Statistics for a single output channel."""

    min: float
    max: float
    mean: float
    std: float
    abs_max: float | None = None
    integrated: float | None = None


class ResultsStatisticsResponse(BaseModel):
    id: str
    simulation_case_id: str
    dlc_number: str
    wind_speed: float
    channel_statistics: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ResultsDELResponse(BaseModel):
    id: str
    simulation_id: str
    del_results: dict | None = None
    m_exponent: float
    n_equivalent: float
    created_at: datetime

    model_config = {"from_attributes": True}


class ResultsExtremeResponse(BaseModel):
    id: str
    simulation_id: str
    extreme_loads: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
