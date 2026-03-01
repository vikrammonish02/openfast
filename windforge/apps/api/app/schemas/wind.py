"""Pydantic schemas for wind environment analysis endpoints."""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Kaimal spectrum
# ---------------------------------------------------------------------------
class KaimalRequest(BaseModel):
    """Request body for Kaimal turbulence spectrum computation."""

    V_hub: float = Field(..., gt=0, description="Hub-height mean wind speed (m/s)")
    freq_min: float = Field(default=0.001, gt=0, description="Minimum frequency (Hz)")
    freq_max: float = Field(default=10.0, gt=0, description="Maximum frequency (Hz)")
    n_points: int = Field(default=500, ge=10, le=5000, description="Number of frequency points")
    turbulence_class: str = Field(default="A", pattern="^[ABCabc]$", description="IEC turbulence class")


class KaimalResponse(BaseModel):
    """Response body for Kaimal spectrum."""

    frequencies: list[float]
    Su: list[float]
    Sv: list[float]
    Sw: list[float]


# ---------------------------------------------------------------------------
# Turbulence envelope
# ---------------------------------------------------------------------------
class TurbulenceEnvelopeRequest(BaseModel):
    """Request body for NTM/ETM turbulence envelope computation."""

    wind_class: str = Field(default="I", description="IEC wind turbine class (I, II, III)")
    v_ref: float = Field(default=50.0, gt=0, description="Reference wind speed (m/s)")


class TurbulenceEnvelopeResponse(BaseModel):
    """Response body for turbulence envelope across all IEC classes."""

    wind_speeds: list[float]
    ntm_A: list[float]
    ntm_B: list[float]
    ntm_C: list[float]
    etm_A: list[float]
    etm_B: list[float]
    etm_C: list[float]


# ---------------------------------------------------------------------------
# Extreme Operating Gust (EOG)
# ---------------------------------------------------------------------------
class EOGRequest(BaseModel):
    """Request body for IEC Extreme Operating Gust computation."""

    V_hub: float = Field(..., gt=0, description="Hub-height mean wind speed (m/s)")
    rotor_diameter: float = Field(..., gt=0, description="Rotor diameter (m)")
    hub_height: float = Field(..., gt=0, description="Hub height (m)")
    wind_class: str = Field(default="I", description="IEC wind turbine class (I, II, III)")
    turbulence_class: str = Field(default="A", pattern="^[ABCabc]$", description="IEC turbulence class")


class EOGResponse(BaseModel):
    """Response body for EOG time series."""

    time: list[float]
    wind_speed: list[float]
    gust_component: list[float]
    gust_peak: float


# ---------------------------------------------------------------------------
# Wind shear profiles
# ---------------------------------------------------------------------------
class WindShearRequest(BaseModel):
    """Request body for wind shear profile computation."""

    V_hub: float = Field(..., gt=0, description="Hub-height mean wind speed (m/s)")
    hub_height: float = Field(..., gt=0, description="Hub height (m)")
    shear_exp: float = Field(default=0.2, ge=0, le=1.0, description="Power-law shear exponent")
    z0: float = Field(default=0.01, gt=0, description="Surface roughness length (m)")
    z_min: float = Field(default=0.0, ge=0, description="Minimum height (m)")
    z_max: float = Field(default=200.0, gt=0, description="Maximum height (m)")
    n_points: int = Field(default=100, ge=10, le=1000, description="Number of height points")


class WindShearResponse(BaseModel):
    """Response body for wind shear profiles."""

    heights: list[float]
    velocity_powerlaw: list[float]
    velocity_loglaw: list[float]
