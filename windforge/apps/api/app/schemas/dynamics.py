"""System dynamics Pydantic v2 schemas for API validation."""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Forced vibration
# ---------------------------------------------------------------------------
class ForcedVibrationRequest(BaseModel):
    zeta_values: list[float] | None = Field(default=None, description="Damping ratios")
    frat_min: float = Field(default=0.0, ge=0, description="Min frequency ratio")
    frat_max: float = Field(default=3.0, le=10, description="Max frequency ratio")
    n_points: int = Field(default=500, ge=50, le=2000, description="Number of points")


class ForcedVibrationResponse(BaseModel):
    frequency_ratios: list[float]
    amplitude_curves: dict[str, list[float]]
    phase_curves: dict[str, list[float]]


# ---------------------------------------------------------------------------
# Bode plot
# ---------------------------------------------------------------------------
class BodePlotRequest(BaseModel):
    mass: float = Field(default=1.0, gt=0, description="Mass (kg)")
    damping: float = Field(default=0.5, ge=0, description="Damping coefficient (Ns/m)")
    stiffness: float = Field(default=10.0, gt=0, description="Stiffness (N/m)")
    freq_min: float = Field(default=0.01, gt=0, description="Min frequency (Hz)")
    freq_max: float = Field(default=100.0, gt=0, description="Max frequency (Hz)")
    n_points: int = Field(default=500, ge=50, le=2000, description="Number of points")


class BodePlotResponse(BaseModel):
    frequencies: list[float]
    magnitude_db: list[float]
    phase_deg: list[float]


# ---------------------------------------------------------------------------
# Step / Impulse response
# ---------------------------------------------------------------------------
class StepImpulseRequest(BaseModel):
    mass: float = Field(default=1.0, gt=0, description="Mass (kg)")
    damping: float = Field(default=0.5, ge=0, description="Damping coefficient (Ns/m)")
    stiffness: float = Field(default=10.0, gt=0, description="Stiffness (N/m)")
    response_type: str = Field(default="step", description="Response type: step, impulse, ramp")
    t_max: float = Field(default=10.0, gt=0, le=100, description="Duration (s)")
    dt: float = Field(default=0.01, gt=0, le=0.5, description="Time step (s)")


class StepImpulseResponse(BaseModel):
    time: list[float]
    displacement: list[float]
    velocity: list[float]


# ---------------------------------------------------------------------------
# Lorenz attractor
# ---------------------------------------------------------------------------
class LorenzRequest(BaseModel):
    sigma: float = Field(default=10.0, description="Lorenz σ parameter")
    rho: float = Field(default=28.0, description="Lorenz ρ parameter")
    beta: float = Field(default=2.6667, description="Lorenz β parameter")
    x0: float = Field(default=1.0, description="Initial x")
    y0: float = Field(default=1.0, description="Initial y")
    z0: float = Field(default=1.0, description="Initial z")
    t_max: float = Field(default=50.0, gt=0, le=200, description="Duration (s)")
    dt: float = Field(default=0.01, gt=0, le=0.5, description="Time step (s)")


class LorenzResponse(BaseModel):
    time: list[float]
    x: list[float]
    y: list[float]
    z: list[float]


# ---------------------------------------------------------------------------
# Pendulum
# ---------------------------------------------------------------------------
class PendulumRequest(BaseModel):
    length: float = Field(default=1.0, gt=0, description="Pendulum length (m)")
    mass: float = Field(default=1.0, gt=0, description="Mass (kg)")
    damping_ratio: float = Field(default=0.0, ge=0, le=2.0, description="Damping ratio")
    theta0: float = Field(default=30.0, description="Initial angle (deg)")
    omega0: float = Field(default=0.0, description="Initial angular velocity (deg/s)")
    t_max: float = Field(default=20.0, gt=0, le=100, description="Duration (s)")
    dt: float = Field(default=0.01, gt=0, le=0.5, description="Time step (s)")


class PendulumResponse(BaseModel):
    time: list[float]
    theta_deg: list[float]
    omega_deg_s: list[float]
    x_pos: list[float]
    y_pos: list[float]
