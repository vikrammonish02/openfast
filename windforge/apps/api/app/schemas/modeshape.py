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
