"""Pydantic schemas for airfoil analysis endpoints."""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Polar analysis (by airfoil_id from DB)
# ---------------------------------------------------------------------------
class PolarAnalysisByIdRequest(BaseModel):
    """Request body for airfoil polar analysis using a DB airfoil_id."""

    airfoil_id: str = Field(..., description="Airfoil ID (UUID or name)")
    re: float | None = Field(default=None, gt=0, description="Reynolds number (picks first if omitted)")


class PolarAnalysisByIdResponse(BaseModel):
    """Response body for polar analysis — includes full arrays for plotting."""

    alpha_deg: list[float]
    cl: list[float]
    cd: list[float]
    cm: list[float]
    cl_cd: list[float]
    cl_max: float
    alpha_stall: float
    cl_cd_max: float
    alpha_0: float
    linear_slope: float


# ---------------------------------------------------------------------------
# Polar analysis (raw arrays)
# ---------------------------------------------------------------------------
class PolarAnalysisRequest(BaseModel):
    """Request body for airfoil polar analysis with raw arrays."""

    alpha: list[float] = Field(..., description="Angle of attack (deg)")
    cl: list[float] = Field(..., description="Lift coefficient array")
    cd: list[float] = Field(..., description="Drag coefficient array")
    cm: list[float] | None = Field(default=None, description="Moment coefficient array")
    re: float = Field(default=1e6, gt=0, description="Reynolds number")


class UnsteadyParams(BaseModel):
    """AeroDyn unsteady aerodynamic parameters."""

    alpha0: float
    alpha1: float
    alpha2: float
    C_nalpha: float
    Cn1: float
    Cn2: float
    Cd0: float
    Cm0: float


class PolarAnalysisResponse(BaseModel):
    """Response body for polar analysis."""

    cl_max: float
    alpha_stall: float
    cl_cd_max: float
    zero_lift_alpha: float
    linear_slope: float
    unsteady_params: UnsteadyParams


# ---------------------------------------------------------------------------
# 3-D correction (by airfoil_id from DB)
# ---------------------------------------------------------------------------
class Correction3DByIdRequest(BaseModel):
    """Request body for 3-D rotational correction using a DB airfoil_id."""

    airfoil_id: str = Field(..., description="Airfoil ID (UUID or name)")
    r_over_R: float = Field(..., gt=0, le=1.0, description="r/R — local radius / rotor radius")
    c_over_R: float = Field(default=0.1, gt=0, description="c/R — chord / rotor radius")
    tsr: float = Field(default=7.0, gt=0, description="Tip-speed ratio")


class Correction3DByIdResponse(BaseModel):
    """Response body for 3-D correction with original + corrected polars."""

    alpha_deg: list[float]
    cl_original: list[float]
    cd_original: list[float]
    cl_corrected: list[float]
    cd_corrected: list[float]


# ---------------------------------------------------------------------------
# 3-D correction (raw arrays)
# ---------------------------------------------------------------------------
class Correction3DRequest(BaseModel):
    """Request body for 3-D rotational correction."""

    alpha: list[float] = Field(..., description="Angle of attack (deg)")
    cl: list[float] = Field(..., description="Lift coefficient array")
    cd: list[float] = Field(..., description="Drag coefficient array")
    r_over_R: float = Field(..., gt=0, le=1.0, description="r/R — local radius / rotor radius")
    chord_over_r: float = Field(..., gt=0, description="c/r — local chord / local radius")
    tsr: float = Field(default=7.0, gt=0, description="Tip-speed ratio")


class Correction3DResponse(BaseModel):
    """Response body for 3-D corrected polar."""

    alpha: list[float]
    cl_corrected: list[float]
    cd_corrected: list[float]


# ---------------------------------------------------------------------------
# Dynamic stall parameters
# ---------------------------------------------------------------------------
class DynamicStallRequest(BaseModel):
    """Request body for dynamic stall parameter extraction."""

    alpha: list[float] = Field(..., description="Angle of attack (deg)")
    cl: list[float] = Field(..., description="Lift coefficient array")
    cd: list[float] = Field(..., description="Drag coefficient array")
    cm: list[float] | None = Field(default=None, description="Moment coefficient array")
    chord: float = Field(default=1.0, gt=0, description="Chord length (m)")
    tau_oye: float = Field(default=4.0, gt=0, description="Oye time constant (chord lengths)")


class DynamicStallResponse(BaseModel):
    """Response body for dynamic stall parameters."""

    mhh_params: dict
    oye_params: dict


# ---------------------------------------------------------------------------
# NACA profile generation
# ---------------------------------------------------------------------------
class NacaRequest(BaseModel):
    """Request body for NACA airfoil profile generation."""

    digits: str = Field(default="0012", min_length=4, max_length=5, description="NACA designation")
    n_points: int = Field(default=100, ge=10, le=1000, description="Points per surface")


class NacaResponse(BaseModel):
    """Response body for NACA profile coordinates."""

    x: list[float]
    y_upper: list[float]
    y_lower: list[float]


# ---------------------------------------------------------------------------
# Dynamic stall simulation
# ---------------------------------------------------------------------------
class DynStallSimRequest(BaseModel):
    """Request for dynamic stall time-domain simulation."""

    alpha: list[float] = Field(..., description="Angle of attack (deg)")
    cl: list[float] = Field(..., description="Lift coefficient array")
    cd: list[float] = Field(..., description="Drag coefficient array")
    cm: list[float] | None = Field(default=None, description="Moment coefficient array")
    chord: float = Field(default=1.0, gt=0, description="Chord length (m)")
    U0: float = Field(default=10.0, gt=0, description="Freestream velocity (m/s)")
    mean_alpha_deg: float = Field(default=8.0, description="Mean AoA (deg)")
    amplitude_deg: float = Field(default=6.0, gt=0, description="Oscillation amplitude (deg)")
    freq: float = Field(default=1.0, gt=0, description="Oscillation frequency (Hz)")
    n_cycles: int = Field(default=4, ge=1, le=20, description="Number of cycles")


class DynStallSimResponse(BaseModel):
    """Response for dynamic stall simulation."""

    time: list[float]
    alpha_dynamic: list[float]
    cl_static: list[float]
    cl_oye: list[float]


# ---------------------------------------------------------------------------
# Wagner function
# ---------------------------------------------------------------------------
class WagnerRequest(BaseModel):
    """Request for Wagner indicial lift response."""

    s_max: float = Field(default=30.0, gt=0, description="Max semi-chord travel")
    n_points: int = Field(default=500, ge=50, le=2000, description="Number of points")


class WagnerResponse(BaseModel):
    """Response for Wagner function."""

    s: list[float]
    phi_jones: list[float]
    phi_openfast: list[float]
