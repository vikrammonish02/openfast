"""BEM & Rotor aerodynamics Pydantic v2 schemas for API validation."""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# CP-Lambda-Pitch surface
# ---------------------------------------------------------------------------
class CpSurfaceRequest(BaseModel):
    """Request body for CP-lambda-pitch surface computation."""

    r: list[float] = Field(..., min_length=3, description="Radial stations (m)")
    chord: list[float] = Field(..., min_length=3, description="Chord distribution (m)")
    twist: list[float] = Field(..., min_length=3, description="Twist distribution (deg)")
    polar_alpha: list[float] = Field(..., min_length=5, description="Polar AoA (deg)")
    polar_cl: list[float] = Field(..., min_length=5, description="Polar Cl")
    polar_cd: list[float] = Field(..., min_length=5, description="Polar Cd")
    V0: float = Field(default=10.0, gt=0, description="Reference wind speed (m/s)")
    nB: int = Field(default=3, ge=1, le=6, description="Number of blades")
    cone: float = Field(default=0.0, ge=-15, le=15, description="Cone angle (deg)")
    R: float | None = Field(default=None, gt=0, description="Rotor radius (m)")
    tsr_min: float = Field(default=1.0, ge=0.1, description="Min tip-speed ratio")
    tsr_max: float = Field(default=15.0, le=30, description="Max tip-speed ratio")
    tsr_steps: int = Field(default=30, ge=5, le=100, description="TSR grid steps")
    pitch_min: float = Field(default=-5.0, description="Min pitch (deg)")
    pitch_max: float = Field(default=25.0, description="Max pitch (deg)")
    pitch_steps: int = Field(default=25, ge=5, le=100, description="Pitch grid steps")


class CpSurfaceResponse(BaseModel):
    """Response with CP-lambda-pitch surface data."""

    tsr_values: list[float]
    pitch_values: list[float]
    cp_matrix: list[list[float]]
    ct_matrix: list[list[float]]
    max_cp: float
    optimal_tsr: float
    optimal_pitch: float


# ---------------------------------------------------------------------------
# Power curve
# ---------------------------------------------------------------------------
class PowerCurveRequest(BaseModel):
    """Request body for aerodynamic power curve computation."""

    r: list[float] = Field(..., min_length=3, description="Radial stations (m)")
    chord: list[float] = Field(..., min_length=3, description="Chord distribution (m)")
    twist: list[float] = Field(..., min_length=3, description="Twist distribution (deg)")
    polar_alpha: list[float] = Field(..., min_length=5, description="Polar AoA (deg)")
    polar_cl: list[float] = Field(..., min_length=5, description="Polar Cl")
    polar_cd: list[float] = Field(..., min_length=5, description="Polar Cd")
    R: float | None = Field(default=None, gt=0, description="Rotor radius (m)")
    nB: int = Field(default=3, ge=1, le=6, description="Number of blades")
    cone: float = Field(default=0.0, ge=-15, le=15, description="Cone angle (deg)")
    rpm: float = Field(default=12.0, gt=0, description="Rotor RPM")
    pitch: float = Field(default=0.0, description="Pitch angle (deg)")
    wind_speeds: list[float] | None = Field(default=None, description="Wind speeds (m/s)")


class PowerCurveResponse(BaseModel):
    """Response with power curve data."""

    wind_speeds: list[float]
    power: list[float]
    thrust: list[float]
    torque: list[float]
    cp: list[float]
    ct: list[float]


# ---------------------------------------------------------------------------
# High thrust corrections
# ---------------------------------------------------------------------------
class HighThrustRequest(BaseModel):
    """Request body for high-thrust correction comparison."""

    methods: list[str] | None = Field(
        default=None,
        description="Correction methods (e.g. Glauert, Spera, Buhl)",
    )
    a_min: float = Field(default=0.0, ge=0, description="Min induction factor")
    a_max: float = Field(default=1.0, le=1.5, description="Max induction factor")
    n_points: int = Field(default=200, ge=20, le=1000, description="Number of points")


class HighThrustResponse(BaseModel):
    """Response with Ct vs a curves for multiple methods."""

    a_values: list[float]
    ct_curves: dict[str, list[float]]


# ---------------------------------------------------------------------------
# Ideal rotor planform
# ---------------------------------------------------------------------------
class IdealRotorRequest(BaseModel):
    """Request body for ideal rotor planform computation."""

    R: float = Field(default=63.0, gt=0, description="Rotor radius (m)")
    r_hub: float = Field(default=1.5, gt=0, description="Hub radius (m)")
    TSR_design: float = Field(default=7.0, gt=0, description="Design tip-speed ratio")
    Cl_design: float = Field(default=1.0, gt=0, description="Design lift coefficient")
    B: int = Field(default=3, ge=1, le=6, description="Number of blades")
    n_points: int = Field(default=50, ge=10, le=200, description="Number of radial stations")


class IdealRotorResponse(BaseModel):
    """Response with ideal rotor chord and twist distributions."""

    r_over_R: list[float]
    chord_wake: list[float]
    twist_wake: list[float]
    chord_nowake: list[float]
    twist_nowake: list[float]
    a_wake: list[float]
    ap_wake: list[float]


# ---------------------------------------------------------------------------
# Optimal CP (Betz limit)
# ---------------------------------------------------------------------------
class OptimalCpRequest(BaseModel):
    """Request body for optimal CP vs TSR computation."""

    tsr_min: float = Field(default=0.5, ge=0.1, description="Min tip-speed ratio")
    tsr_max: float = Field(default=15.0, le=30, description="Max tip-speed ratio")
    n_points: int = Field(default=200, ge=20, le=1000, description="Number of points")


class OptimalCpResponse(BaseModel):
    """Response with optimal CP and induction vs TSR."""

    tsr: list[float]
    cp_optimal: list[float]
    cp_betz: list[float]
    a_optimal: list[float]
    ap_optimal: list[float]


# ---------------------------------------------------------------------------
# Wake expansion
# ---------------------------------------------------------------------------
class WakeExpansionRequest(BaseModel):
    """Request body for wake expansion computation."""

    CT: float = Field(default=0.8, gt=0, le=2.0, description="Thrust coefficient")
    models: list[str] | None = Field(
        default=None,
        description="Wake models (e.g. momentum, cylinder, Rathmann, Frandsen)",
    )
    x_max_over_D: float = Field(default=20.0, gt=0, le=100, description="Max downstream distance (D)")
    n_points: int = Field(default=200, ge=20, le=1000, description="Number of points")


class WakeExpansionResponse(BaseModel):
    """Response with wake expansion r/R vs x/D for multiple models."""

    x_over_D: list[float]
    curves: dict[str, list[float]]


# ---------------------------------------------------------------------------
# Dynamic inflow
# ---------------------------------------------------------------------------
class DynamicInflowRequest(BaseModel):
    """Request body for Øye dynamic inflow simulation."""

    R: float = Field(default=63.0, gt=0, description="Rotor radius (m)")
    U0: float = Field(default=10.0, gt=0, description="Free-stream wind speed (m/s)")
    a_init: float = Field(default=0.2, ge=0, le=0.9, description="Initial induction factor")
    a_final: float = Field(default=0.35, ge=0, le=0.9, description="Final induction factor")
    r_bar: float = Field(default=0.7, gt=0, le=1.0, description="Normalised radial position r/R")
    t_max: float = Field(default=30.0, gt=0, le=300, description="Simulation duration (s)")
    dt: float = Field(default=0.05, gt=0, le=1.0, description="Time step (s)")


class DynamicInflowResponse(BaseModel):
    """Response with dynamic vs quasi-steady induction time series."""

    time: list[float]
    a_dynamic: list[float]
    a_quasi_steady: list[float]
    tau1: float
    tau2: float
