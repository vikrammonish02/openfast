"""Potential flow Pydantic v2 schemas for API validation."""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Vortex point
# ---------------------------------------------------------------------------
class VortexPointRequest(BaseModel):
    Gamma: float = Field(default=1.0, description="Circulation strength")
    x_min: float = Field(default=-3.0, description="Grid x-min")
    x_max: float = Field(default=3.0, description="Grid x-max")
    y_min: float = Field(default=-3.0, description="Grid y-min")
    y_max: float = Field(default=3.0, description="Grid y-max")
    n_grid: int = Field(default=80, ge=20, le=200, description="Grid resolution")
    vortex_x: float = Field(default=0.0, description="Vortex x-position")
    vortex_y: float = Field(default=0.0, description="Vortex y-position")


class VortexPointResponse(BaseModel):
    x: list[float]
    y: list[float]
    U: list[list[float]]
    V: list[list[float]]
    speed: list[list[float]]
    psi: list[list[float]]


# ---------------------------------------------------------------------------
# Cylinder flow
# ---------------------------------------------------------------------------
class CylinderFlowRequest(BaseModel):
    U0: float = Field(default=1.0, gt=0, description="Freestream speed")
    R: float = Field(default=1.0, gt=0, description="Cylinder radius")
    Gamma: float = Field(default=0.0, description="Circulation (+ = CCW)")
    alpha_deg: float = Field(default=0.0, description="Angle of attack (deg)")
    x_min: float = Field(default=-4.0, description="Grid x-min")
    x_max: float = Field(default=4.0, description="Grid x-max")
    y_min: float = Field(default=-3.0, description="Grid y-min")
    y_max: float = Field(default=3.0, description="Grid y-max")
    n_grid: int = Field(default=100, ge=20, le=200, description="Grid resolution")
    n_theta: int = Field(default=200, ge=50, le=500, description="Surface Cp points")


class CylinderFlowResponse(BaseModel):
    x: list[float]
    y: list[float]
    U: list[list[float]]
    V: list[list[float]]
    speed: list[list[float]]
    xc: list[float]
    yc: list[float]
    stag_x: list[float]
    stag_y: list[float]
    theta_deg: list[float]
    Cp_theta: list[float]


# ---------------------------------------------------------------------------
# Karman-Trefftz airfoil
# ---------------------------------------------------------------------------
class KarmanTrefftzRequest(BaseModel):
    XC: float = Field(default=-0.2, description="Cylinder center X (mapping plane)")
    YC: float = Field(default=0.1, description="Cylinder center Y (mapping plane)")
    tau_deg: float = Field(default=10.0, ge=1, le=45, description="Trailing edge angle (deg)")
    alpha_deg: float = Field(default=5.0, description="Angle of attack (deg)")
    U0: float = Field(default=1.0, gt=0, description="Freestream speed")
    A: float = Field(default=1.0, gt=0, description="Cylinder x-intercept")
    n_surface: int = Field(default=150, ge=20, le=500, description="Surface points")
    n_grid: int = Field(default=120, ge=20, le=200, description="Flow field resolution")


class KarmanTrefftzResponse(BaseModel):
    airfoil_x: list[float]
    airfoil_y: list[float]
    wall_x: list[float]
    wall_y: list[float]
    wall_Cp: list[float]
    x: list[float]
    y: list[float]
    u_field: list[list[float]]
    v_field: list[list[float]]
    Cp_field: list[list[float]]
    speed_field: list[list[float]]
