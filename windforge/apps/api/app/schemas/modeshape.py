"""Mode shape analysis Pydantic schemas for API validation."""

from pydantic import BaseModel, Field


class ModeShapeRequest(BaseModel):
    """Request body for mode shape computation."""

    turbine_model_id: str
    component: str = Field(
        default="tower",
        description="Component to analyse: 'tower' or 'blade'.",
    )
    n_modes: int = Field(default=5, ge=1, le=20)
    include_tip_mass: bool = Field(
        default=False,
        description="Include RNA mass at tower top (tower only).",
    )


class ModeData(BaseModel):
    """A single computed mode shape."""

    frequency: float
    label: str
    shape_values: list[float]
    shape_values_edge: list[float] | None = None


class ModeShapeResponse(BaseModel):
    """Response with computed mode shapes."""

    component: str
    span_positions: list[float]
    modes: list[ModeData]


class DeflectionRequest(BaseModel):
    """Request body for static deflection computation."""

    turbine_model_id: str
    component: str = Field(
        default="tower",
        description="Component to analyse: 'tower' or 'blade'.",
    )
    tip_load: float = Field(default=0.0, ge=0, description="Point force at tip [N].")
    distributed_load: float = Field(
        default=0.0, ge=0, description="Uniform distributed load [N/m]."
    )


class DeflectionResponse(BaseModel):
    """Response with static deflection results."""

    span_positions: list[float]
    deflection: list[float]


# ---------------------------------------------------------------------------
# Uniform beam theory modes
# ---------------------------------------------------------------------------
class BeamTheoryRequest(BaseModel):
    """Request for analytical uniform beam bending modes."""

    BC_type: str = Field(
        default="unloaded-clamped-free",
        description="Boundary condition string",
    )
    EI: float = Field(default=2.1e8, gt=0, description="Flexural rigidity (Nm^2)")
    rho: float = Field(default=7850.0, gt=0, description="Density (kg/m^3)")
    A: float = Field(default=0.01, gt=0, description="Cross-section area (m^2)")
    L: float = Field(default=10.0, gt=0, description="Beam length (m)")
    n_modes: int = Field(default=4, ge=1, le=10, description="Number of modes")
    Mtop: float = Field(default=0.0, ge=0, description="Tip mass (kg)")


class BeamTheoryModeData(BaseModel):
    frequency: float
    label: str
    shape_values: list[float]


class BeamTheoryResponse(BaseModel):
    x: list[float]
    frequencies: list[float]
    modes: list[BeamTheoryModeData]


# ---------------------------------------------------------------------------
# FEM vs Theory comparison
# ---------------------------------------------------------------------------
class FemCompareRequest(BaseModel):
    """Request for FEM vs analytical beam comparison."""

    EI: float = Field(default=2.1e8, gt=0, description="Flexural rigidity (Nm^2)")
    rho: float = Field(default=7850.0, gt=0, description="Density (kg/m^3)")
    A: float = Field(default=0.01, gt=0, description="Cross-section area (m^2)")
    L: float = Field(default=10.0, gt=0, description="Beam length (m)")
    n_modes: int = Field(default=4, ge=1, le=10, description="Number of modes")
    n_elements: int = Field(default=20, ge=5, le=100, description="FEM elements")


class FemCompareResponse(BaseModel):
    x_theory: list[float]
    x_fem: list[float]
    frequencies_theory: list[float]
    frequencies_fem: list[float]
    modes_theory: list[BeamTheoryModeData]
    modes_fem: list[BeamTheoryModeData]
