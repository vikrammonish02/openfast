"""Particle dynamics Pydantic v2 schemas for API validation."""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Free fall
# ---------------------------------------------------------------------------
class FreeFallRequest(BaseModel):
    mass: float = Field(default=10.0, gt=0, description="Mass (kg)")
    z0: float = Field(default=100.0, description="Initial height (m)")
    vx0: float = Field(default=5.0, description="Initial horizontal velocity (m/s)")
    vz0: float = Field(default=0.0, description="Initial vertical velocity (m/s)")
    g: float = Field(default=9.81, gt=0, description="Gravity (m/s^2)")
    t_max: float = Field(default=5.0, gt=0, le=100, description="Duration (s)")
    n_points: int = Field(default=200, ge=50, le=2000, description="Number of points")


class FreeFallResponse(BaseModel):
    time: list[float]
    x: list[float]
    z: list[float]
    vx: list[float]
    vz: list[float]
    z_analytical: list[float]


# ---------------------------------------------------------------------------
# Orbital motion
# ---------------------------------------------------------------------------
class OrbitRequest(BaseModel):
    m1: float = Field(default=5.972e24, gt=0, description="Central body mass (kg)")
    m2: float = Field(default=7.348e22, gt=0, description="Orbiting body mass (kg)")
    r_initial: float = Field(default=3.844e8, gt=0, description="Initial separation (m)")
    eccentricity: float = Field(default=0.0, ge=0, lt=1.0, description="Orbital eccentricity")
    n_orbits: float = Field(default=2.0, gt=0, le=10, description="Number of orbits")
    n_points: int = Field(default=1000, ge=100, le=5000, description="Number of points")


class OrbitResponse(BaseModel):
    time: list[float]
    x1: list[float]
    z1: list[float]
    x2: list[float]
    z2: list[float]
    energy_kinetic: list[float]
    energy_potential: list[float]


# ---------------------------------------------------------------------------
# Spring-mass
# ---------------------------------------------------------------------------
class SpringMassRequest(BaseModel):
    m: float = Field(default=10.0, gt=0, description="Mass (kg)")
    k: float = Field(default=100.0, gt=0, description="Spring stiffness (N/m)")
    c: float = Field(default=0.0, ge=0, description="Damping coefficient (Ns/m)")
    z0_offset: float = Field(default=2.0, description="Initial offset from equilibrium (m)")
    g: float = Field(default=9.81, gt=0, description="Gravity (m/s^2)")
    t_max: float = Field(default=10.0, gt=0, le=100, description="Duration (s)")
    n_points: int = Field(default=500, ge=50, le=2000, description="Number of points")


class SpringMassResponse(BaseModel):
    time: list[float]
    z: list[float]
    vz: list[float]
    energy_kinetic: list[float]
    energy_spring: list[float]
    energy_total: list[float]
