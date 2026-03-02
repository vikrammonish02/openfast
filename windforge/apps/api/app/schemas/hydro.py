"""Hydrodynamics Pydantic v2 schemas for API validation."""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Wave kinematics
# ---------------------------------------------------------------------------
class WaveKinematicsRequest(BaseModel):
    """Request body for wave kinematics computation."""

    Hs: float = Field(..., gt=0, description="Significant wave height (m)")
    Tp: float = Field(..., gt=0, description="Peak spectral period (s)")
    water_depth: float = Field(..., gt=0, description="Water depth (m)")
    time_duration: float = Field(default=60.0, gt=0, description="Time duration (s)")
    n_freq: int = Field(default=200, ge=10, le=2000, description="Number of frequency components")


class WaveKinematicsResponse(BaseModel):
    """Response with wave elevation, velocity, and acceleration fields."""

    time: list[float]
    elevation: list[float]
    z_positions: list[float]
    velocity: list[list[float]]
    acceleration: list[list[float]]


# ---------------------------------------------------------------------------
# JONSWAP spectrum
# ---------------------------------------------------------------------------
class JonswapRequest(BaseModel):
    """Request body for JONSWAP spectrum computation."""

    Hs: float = Field(..., gt=0, description="Significant wave height (m)")
    Tp: float = Field(..., gt=0, description="Peak spectral period (s)")
    freq_min: float = Field(default=0.01, gt=0, description="Minimum frequency (Hz)")
    freq_max: float = Field(default=0.5, gt=0, description="Maximum frequency (Hz)")
    n_points: int = Field(default=500, ge=10, le=5000, description="Number of frequency points")


class JonswapResponse(BaseModel):
    """Response with JONSWAP spectral density curve."""

    frequencies: list[float]
    spectral_density: list[float]


# ---------------------------------------------------------------------------
# Morison loads
# ---------------------------------------------------------------------------
class MorisonRequest(BaseModel):
    """Request body for Morison load computation on a monopile."""

    Hs: float = Field(..., gt=0, description="Significant wave height (m)")
    Tp: float = Field(..., gt=0, description="Peak spectral period (s)")
    water_depth: float = Field(..., gt=0, description="Water depth (m)")
    monopile_diameter: float = Field(..., gt=0, description="Monopile diameter (m)")
    Cd: float = Field(default=1.0, ge=0, description="Drag coefficient")
    Cm: float = Field(default=2.0, ge=0, description="Inertia coefficient")
    time_duration: float = Field(default=60.0, gt=0, description="Time duration (s)")


class MorisonResponse(BaseModel):
    """Response with Morison base shear and overturning moment time series."""

    time: list[float]
    base_shear: list[float]
    overturning_moment: list[float]
    max_base_shear: float
    max_moment: float


# ---------------------------------------------------------------------------
# Hydrostatic properties
# ---------------------------------------------------------------------------
class HydrostaticRequest(BaseModel):
    """Request body for hydrostatic restoring and added-mass computation."""

    radius: float = Field(..., gt=0, description="Cylinder radius (m)")
    z_bottom: float = Field(..., description="Bottom position (m, negative below MSL)")
    z_top: float = Field(..., description="Top position (m, positive above MSL if piercing)")
    rho_water: float = Field(default=1025.0, gt=0, description="Water density (kg/m^3)")
    mass_structure: float = Field(default=0.0, ge=0, description="Structure mass (kg)")
    z_cg: float = Field(default=0.0, description="Centre of gravity z-position (m)")


class HydrostaticResponse(BaseModel):
    """Response with 6x6 hydrostatic stiffness and added-mass matrices."""

    stiffness_matrix: list[list[float]]
    added_mass_matrix: list[list[float]]
