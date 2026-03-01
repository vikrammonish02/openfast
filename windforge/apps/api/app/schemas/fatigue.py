"""Pydantic schemas for fatigue analysis endpoints."""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Equivalent load (DEL)
# ---------------------------------------------------------------------------
class EquivalentLoadRequest(BaseModel):
    """Request body for damage equivalent load computation from simulation output."""

    simulation_id: str = Field(..., description="Simulation ID")
    case_id: str = Field(..., description="Simulation case ID")
    channel: str = Field(..., description="Output channel name (e.g. 'TwrBsMyt')")
    m_exponents: list[int] = Field(
        default=[3, 4, 10, 12],
        description="Woehler exponents to evaluate",
    )
    Teq: float = Field(default=600.0, gt=0, description="Equivalent period (s)")


class EquivalentLoadResponse(BaseModel):
    """Response body for DEL computation."""

    channel: str
    m_exponents: list[int]
    del_values: list[float]
    Teq: float


# ---------------------------------------------------------------------------
# Direct DEL from raw data (no DB lookup)
# ---------------------------------------------------------------------------
class EquivalentLoadDirectRequest(BaseModel):
    """Request body for DEL computation from directly-provided time series."""

    time: list[float] = Field(..., description="Time vector (s)")
    signal: list[float] = Field(..., description="Load signal array")
    m_exponents: list[int] = Field(
        default=[3, 4, 10, 12],
        description="Woehler exponents to evaluate",
    )
    Teq: float = Field(default=600.0, gt=0, description="Equivalent period (s)")


class EquivalentLoadDirectResponse(BaseModel):
    """Response body for direct DEL computation."""

    m_exponents: list[int]
    del_values: list[float]
    Teq: float


# ---------------------------------------------------------------------------
# Rainflow cycles
# ---------------------------------------------------------------------------
class RainflowRequest(BaseModel):
    """Request body for rainflow cycle counting from simulation output."""

    simulation_id: str = Field(..., description="Simulation ID")
    case_id: str = Field(..., description="Simulation case ID")
    channel: str = Field(..., description="Output channel name")


class RainflowResponse(BaseModel):
    """Response body for rainflow cycle counting."""

    channel: str
    ranges: list[float]
    counts: list[float]
    bins: list[float]
    del_m3: float
