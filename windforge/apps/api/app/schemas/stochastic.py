"""Stochastic & signal processing Pydantic v2 schemas for API validation."""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Probability distributions
# ---------------------------------------------------------------------------
class DistributionsRequest(BaseModel):
    distributions: list[dict] | None = Field(
        default=None,
        description="List of {type, params, label} dicts.  If None, defaults are used.",
    )
    x_min: float = Field(default=-5.0, description="X-axis minimum")
    x_max: float = Field(default=15.0, description="X-axis maximum")
    n_points: int = Field(default=500, ge=50, le=5000, description="Number of points")


class DistributionsResponse(BaseModel):
    x: list[float]
    curves: dict[str, list[float]]


# ---------------------------------------------------------------------------
# Stochastic process
# ---------------------------------------------------------------------------
class StochasticProcessRequest(BaseModel):
    process_type: str = Field(
        default="harmonic",
        description="One of: harmonic, exponential, banded_white_noise",
    )
    omega_max: float = Field(default=10.0, gt=0, description="Max angular frequency")
    tau_max: float = Field(default=10.0, gt=0, description="Max lag")
    time_max: float = Field(default=50.0, gt=0, le=500, description="Duration")
    n_discr: int = Field(default=200, ge=50, le=2000, description="Discretisation points")


class StochasticProcessResponse(BaseModel):
    time: list[float]
    signal: list[float]
    tau: list[float]
    autocovariance: list[float]
    freq: list[float]
    autospectrum: list[float]


# ---------------------------------------------------------------------------
# FFT / PSD
# ---------------------------------------------------------------------------
class FftPsdRequest(BaseModel):
    time: list[float] = Field(description="Time array")
    signal: list[float] = Field(description="Signal values")
    output_type: str = Field(default="PSD", description="'amplitude', 'PSD', or 'f x psd'")
    averaging: str = Field(default="Welch", description="'none' or 'Welch'")


class FftPsdResponse(BaseModel):
    frequencies: list[float]
    spectrum: list[float]


# ---------------------------------------------------------------------------
# Correlation
# ---------------------------------------------------------------------------
class CorrelationRequest(BaseModel):
    coeff: float = Field(default=0.95, ge=-1, le=1, description="Correlation coefficient")
    n_points: int = Field(default=2000, ge=100, le=10000, description="Signal length")
    n_lags: int = Field(default=200, ge=10, le=2000, description="Number of lags")


class CorrelationResponse(BaseModel):
    signal: list[float]
    lags: list[float]
    correlation_values: list[float]
    theoretical_coeff: float


# ---------------------------------------------------------------------------
# Turbulent wind generation
# ---------------------------------------------------------------------------
class TurbulentWindRequest(BaseModel):
    U0: float = Field(default=10.0, gt=0, description="Mean wind speed (m/s)")
    turbulence_intensity: float = Field(
        default=0.14, gt=0, le=1.0, description="Turbulence intensity"
    )
    L: float = Field(default=340.2, gt=0, description="Turbulence length scale (m)")
    t_max: float = Field(default=300.0, gt=0, le=3600, description="Duration (s)")
    dt: float = Field(default=0.05, gt=0, le=1.0, description="Time step (s)")
    seed: int = Field(default=42, description="Random seed")


class TurbulentWindResponse(BaseModel):
    time: list[float]
    velocity: list[float]
    frequencies_generated: list[float]
    spectrum_generated: list[float]
    frequencies_target: list[float]
    spectrum_target: list[float]
