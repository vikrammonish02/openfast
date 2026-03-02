"""Reference turbine template schemas."""

from pydantic import BaseModel, Field


class TemplateInfo(BaseModel):
    """Metadata about a reference turbine template."""
    id: str
    name: str
    description: str
    rated_power_kw: float
    rotor_diameter: float
    hub_height: float
    wind_class: str
    turbulence_class: str
    platform_type: str
    is_offshore: bool


class CreateFromTemplateRequest(BaseModel):
    """Request to create a project from a reference turbine template."""
    template_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    platform_type: str | None = None  # Override template default
