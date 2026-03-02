"""Post-processing Pydantic v2 schemas for API validation."""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# DEL & Fatigue
# ---------------------------------------------------------------------------
class DelFatigueRequest(BaseModel):
    signal_type: str = Field(default="sine_noise", description="Signal type: sine_noise, random_walk")
    amplitude: float = Field(default=1000.0, gt=0, description="Load amplitude (N or N-m)")
    frequency: float = Field(default=0.5, gt=0, le=50.0, description="Primary frequency (Hz)")
    noise_std: float = Field(default=200.0, ge=0, description="Noise std dev")
    mean_load: float = Field(default=500.0, description="Mean load level")
    duration: float = Field(default=600.0, gt=0, le=3600.0, description="Duration (s)")
    dt: float = Field(default=0.05, gt=0.001, le=1.0, description="Time step (s)")
    wohler_exponents: list[float] = Field(default=[3.0, 4.0, 6.0, 8.0, 10.0, 12.0], description="Wohler exponents")
    n_bins: int = Field(default=46, ge=10, le=200, description="Number of bins for rainflow")
    rainflow_method: str = Field(default="windap", description="Rainflow method: windap or astm")


class DelFatigueResponse(BaseModel):
    time: list[float]
    signal: list[float]
    del_values: dict[str, float]
    rainflow_ranges: list[float]
    rainflow_counts: list[float]
    markov_cycles: list[list[float]]
    markov_ampl_edges: list[float]
    markov_mean_edges: list[float]


# ---------------------------------------------------------------------------
# Statistics & PDF
# ---------------------------------------------------------------------------
class StatisticsRequest(BaseModel):
    signal_type: str = Field(default="sine_noise", description="Signal type: sine_noise, gaussian, uniform")
    amplitude: float = Field(default=5.0, gt=0, description="Signal amplitude")
    frequency: float = Field(default=1.0, gt=0, le=100.0, description="Frequency (Hz)")
    noise_std: float = Field(default=2.0, ge=0, description="Noise std dev")
    mean_val: float = Field(default=0.0, description="Mean value")
    duration: float = Field(default=60.0, gt=0, le=600.0, description="Duration (s)")
    dt: float = Field(default=0.01, gt=0.001, le=1.0, description="Time step (s)")
    pdf_method: str = Field(default="histogram", description="PDF method: histogram, gaussian_kde")
    n_bins: int = Field(default=50, ge=10, le=500, description="Number of bins")


class StatsDict(BaseModel):
    mean: float
    std: float
    min: float
    max: float
    rms: float
    skewness: float
    kurtosis: float


class StatisticsResponse(BaseModel):
    time: list[float]
    signal: list[float]
    pdf_x: list[float]
    pdf_y: list[float]
    stats: StatsDict


# ---------------------------------------------------------------------------
# Spectral Analysis
# ---------------------------------------------------------------------------
class SpectralRequest(BaseModel):
    signal_type: str = Field(default="multi_sine", description="Signal type")
    frequencies: list[float] = Field(default=[0.5, 1.2, 3.0], description="Component frequencies (Hz)")
    amplitudes: list[float] = Field(default=[2.0, 1.0, 0.5], description="Component amplitudes")
    noise_std: float = Field(default=0.5, ge=0, description="Noise std dev")
    duration: float = Field(default=100.0, gt=0, le=1000.0, description="Duration (s)")
    dt: float = Field(default=0.01, gt=0.001, le=1.0, description="Time step (s)")
    output_type: str = Field(default="PSD", description="Output: amplitude, PSD, f x PSD")
    averaging: str = Field(default="Welch", description="Averaging: None, Welch, Binning")
    averaging_window: str = Field(default="hamming", description="Window: hamming, hann, rectangular")


class SpectralResponse(BaseModel):
    time: list[float]
    signal: list[float]
    freq: list[float]
    spectrum: list[float]
    output_type: str


# ---------------------------------------------------------------------------
# Damping Estimation
# ---------------------------------------------------------------------------
class DampingRequest(BaseModel):
    natural_freq: float = Field(default=0.1, gt=0, le=10.0, description="Natural frequency (Hz)")
    damping_ratio: float = Field(default=0.05, gt=0.001, lt=1.0, description="Damping ratio")
    amplitude: float = Field(default=10.0, gt=0, description="Initial amplitude")
    mean_offset: float = Field(default=5.0, description="Mean offset")
    duration: float = Field(default=200.0, gt=0, le=1000.0, description="Duration (s)")
    dt: float = Field(default=0.05, gt=0.001, le=1.0, description="Time step (s)")


class DampingEstimated(BaseModel):
    fn: float
    fd: float
    zeta: float
    zetaMin: float
    zetaMax: float
    omega0: float
    Td: float


class DampingInputParams(BaseModel):
    fn_true: float
    zeta_true: float


class DampingResponse(BaseModel):
    time: list[float]
    signal: list[float]
    x_model: list[float]
    epos: list[float]
    eneg: list[float]
    peaks_pos_t: list[float]
    peaks_pos_x: list[float]
    peaks_neg_t: list[float]
    peaks_neg_x: list[float]
    estimated: DampingEstimated
    input_params: DampingInputParams


# ---------------------------------------------------------------------------
# Extreme Value Extrapolation (Gumbel / EV1)
# ---------------------------------------------------------------------------
class ExtremeValueRequest(BaseModel):
    signal_type: str = Field(default="turbulent_load", description="Signal type: turbulent_load, weibull_process")
    amplitude: float = Field(default=2000.0, gt=0, description="Load amplitude (N)")
    frequency: float = Field(default=0.3, gt=0, le=50.0, description="Primary frequency (Hz)")
    noise_std: float = Field(default=500.0, ge=0, description="Noise std dev (N)")
    mean_load: float = Field(default=3000.0, description="Mean load level (N)")
    duration: float = Field(default=600.0, gt=0, le=3600.0, description="Duration per simulation (s)")
    dt: float = Field(default=0.05, gt=0.001, le=1.0, description="Time step (s)")
    n_simulations: int = Field(default=6, ge=2, le=100, description="Number of independent simulations (seeds)")
    block_size: float = Field(default=600.0, gt=0, le=3600.0, description="Block size for maxima extraction (s)")
    threshold_sigma: float = Field(default=1.4, gt=0, le=5.0, description="Threshold = mean + sigma * this")
    return_periods: list[float] = Field(default=[1.0, 10.0, 50.0, 100.0, 500.0, 1000.0], description="Return periods")


class GumbelParams(BaseModel):
    alpha: float
    beta: float
    mu: float
    sigma: float
    n_extremes: int


class ExtremeValueResponse(BaseModel):
    time: list[float]
    signal: list[float]
    block_maxima: list[float]
    gumbel_params: GumbelParams
    prob_plot_x: list[float]
    prob_plot_y: list[float]
    prob_plot_fit_x: list[float]
    prob_plot_fit_y: list[float]
    return_periods: list[str]
    extrapolated_loads: dict[str, float]
    confidence_95_lower: dict[str, float]
    confidence_95_upper: dict[str, float]
    pot_threshold: float
    pot_peaks_t: list[float]
    pot_peaks_x: list[float]


# ---------------------------------------------------------------------------
# IEC Loads Analysis (real simulation data)
# ---------------------------------------------------------------------------
class IECLoadsRequest(BaseModel):
    """Request to run IEC 61400-1 loads analysis on real simulation output files."""

    simulation_id: str = Field(..., description="Simulation to analyze")
    case_ids: list[str] | None = Field(
        default=None,
        description="Specific case IDs to include. None = all completed cases.",
    )
    dlc_filter: list[str] | None = Field(
        default=None,
        description="Filter by DLC numbers (e.g. ['1.1', '1.3']). None = all DLCs.",
    )
    channels: list[str] | None = Field(
        default=None,
        description="Specific channels to analyze. None = all common channels.",
    )
    t_start: float = Field(default=30.0, ge=0, description="Skip initial transient (s)")
    wohler_exponents: list[float] = Field(
        default=[3.0, 4.0, 6.0, 8.0, 10.0, 12.0],
        description="Wöhler exponents for fatigue DEL",
    )
    n_equivalent: float = Field(default=1e7, gt=0, description="Equivalent cycle count for DEL")
    consequence_factor: float = Field(
        default=1.0,
        ge=1.0,
        le=1.3,
        description="Consequence of failure factor γn (IEC Table 3)",
    )


class IECExtremeLoadRow(BaseModel):
    """A single row in the IEC extreme loads table."""

    channel: str
    unit: str
    max_characteristic: float
    max_design: float
    max_dlc: str
    max_vhub: float
    max_time: float
    max_case_id: str
    min_characteristic: float
    min_design: float
    min_dlc: str
    min_vhub: float
    min_time: float
    min_case_id: str
    safety_factor_max: float
    safety_factor_min: float


class IECConcurrentLoadEntry(BaseModel):
    """Concurrent loads at the timestep of a governing extreme."""

    governing_channel: str
    extreme_type: str  # "max" or "min"
    timestep_values: dict[str, float]


class IECDELRow(BaseModel):
    """A single row in the fatigue DEL table."""

    channel: str
    unit: str
    del_values: dict[str, float]  # "m=3" -> value
    n_equivalent: float


class IECStatisticsRow(BaseModel):
    """A single row in the statistics summary table."""

    channel: str
    unit: str
    mean: float
    std: float
    min_val: float
    max_val: float
    abs_max: float
    n_cases: int


class IECCaseSummaryRow(BaseModel):
    """Summary of a simulation case included in the analysis."""

    case_id: str
    dlc_number: str
    wind_speed: float
    seed_number: int
    yaw_misalignment: float
    analysis_type: str
    safety_factor: float
    probability_weight: float


class IECLoadsResponse(BaseModel):
    """Full IEC loads analysis response with all tables."""

    simulation_id: str
    simulation_name: str
    n_cases_analyzed: int
    channels_analyzed: list[str]
    extreme_loads: list[IECExtremeLoadRow]
    concurrent_loads: list[IECConcurrentLoadEntry]
    del_table: list[IECDELRow]
    statistics_table: list[IECStatisticsRow]
    case_summary: list[IECCaseSummaryRow]


class IECSimulationInfo(BaseModel):
    """Simulation info for the selector dropdown."""

    id: str
    name: str
    status: str
    total_cases: int
    completed_cases: int
    failed_cases: int
    dlc_numbers: list[str]
    created_at: str


class IECCaseInfo(BaseModel):
    """Case info for the case selector."""

    case_id: str
    dlc_number: str
    wind_speed: float
    seed_number: int
    yaw_misalignment: float
    analysis_type: str
    safety_factor: float
    probability_weight: float
    status: str


class IECCasesGrouped(BaseModel):
    """Cases grouped by DLC number."""

    dlc_number: str
    cases: list[IECCaseInfo]
    total_cases: int
    completed_cases: int


# ---------------------------------------------------------------------------
# IEC Gumbel Extreme Value Extrapolation (real simulation data)
# ---------------------------------------------------------------------------
class IECGumbelRequest(BaseModel):
    """Request for Gumbel extrapolation on real simulation outputs."""

    simulation_id: str = Field(..., description="Simulation to analyze")
    channel: str = Field(..., description="Channel to fit Gumbel distribution to")
    case_ids: list[str] | None = Field(
        default=None,
        description="Specific case IDs to include. None = all completed cases.",
    )
    dlc_filter: list[str] | None = Field(
        default=None,
        description="Filter by DLC numbers (e.g. ['1.1']). None = all DLCs.",
    )
    t_start: float = Field(default=30.0, ge=0, description="Skip initial transient (s)")
    block_size: float = Field(
        default=600.0,
        gt=0,
        le=3600.0,
        description="Block size for maxima extraction (s)",
    )
    threshold_sigma: float = Field(
        default=1.4,
        gt=0,
        le=5.0,
        description="POT threshold = mean + sigma * this",
    )
    return_periods: list[float] = Field(
        default=[1.0, 10.0, 50.0, 100.0, 500.0, 1000.0],
        description="Return periods for extrapolation",
    )


class ExceedanceFitCurve(BaseModel):
    """A single fitted distribution curve for the exceedance plot."""

    x: list[float]
    y: list[float]


class IECGumbelResponse(BaseModel):
    """NREL-style extreme value extrapolation results with exceedance plot data."""

    channel: str
    n_cases: int
    n_blocks: int
    n_peaks: int
    time: list[float]
    signal: list[float]
    block_maxima: list[float]
    gumbel_params: GumbelParams
    prob_plot_x: list[float]
    prob_plot_y: list[float]
    prob_plot_fit_x: list[float]
    prob_plot_fit_y: list[float]
    return_periods: list[str]
    extrapolated_loads: dict[str, float]
    confidence_95_lower: dict[str, float]
    confidence_95_upper: dict[str, float]
    case_block_info: list[dict]
    # NREL-style exceedance probability plot data
    exceedance_data_x: list[float]
    exceedance_data_y: list[float]
    exceedance_fits: dict[str, ExceedanceFitCurve]
    pot_threshold: float
    distribution_params: dict


class IECChannelListResponse(BaseModel):
    """List of available channels for a simulation."""

    simulation_id: str
    channels: list[str]
