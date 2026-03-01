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
