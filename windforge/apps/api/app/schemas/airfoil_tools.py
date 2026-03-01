"""Pydantic schemas for airfoil analysis endpoints."""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Polar analysis
# ---------------------------------------------------------------------------
class PolarAnalysisRequest(BaseModel):
    """Request body for airfoil polar analysis."""

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
# 3-D correction
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
