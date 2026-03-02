"""Project schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    """Payload for creating a new project."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None

    # IEC wind class
    wind_class: str | None = Field(None, pattern=r"^(I|II|III|S)$")
    turbulence_class: str | None = Field(None, pattern=r"^(A|B|C)$")
    v_ref: float | None = None
    i_ref: float | None = None

    # Turbine parameters
    rated_power: float | None = None
    rotor_diameter: float | None = None
    hub_height: float | None = None
    num_blades: int | None = Field(None, ge=1, le=5)
    cut_in_speed: float | None = None
    cut_out_speed: float | None = None
    rated_speed: float | None = None

    # Simulation defaults
    dt: float | None = Field(None, gt=0, le=1.0)
    t_max: float | None = Field(None, gt=0)

    platform_type: str = Field(default="onshore", pattern=r"^(onshore|monopile|jacket|spar|semi_submersible|tlp)$")
    water_depth: float | None = Field(None, ge=0)


class ProjectUpdate(BaseModel):
    """Payload for partially updating a project."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    wind_class: str | None = None
    turbulence_class: str | None = None
    v_ref: float | None = None
    i_ref: float | None = None
    rated_power: float | None = None
    rotor_diameter: float | None = None
    hub_height: float | None = None
    num_blades: int | None = None
    cut_in_speed: float | None = None
    cut_out_speed: float | None = None
    rated_speed: float | None = None
    dt: float | None = None
    t_max: float | None = None
    platform_type: str | None = None
    water_depth: float | None = None
    status: str | None = None


class ProjectResponse(BaseModel):
    """Public representation of a project."""

    id: str
    org_id: str
    created_by: str | None = None
    name: str
    description: str | None = None

    wind_class: str | None = None
    turbulence_class: str | None = None
    v_ref: float | None = None
    i_ref: float | None = None

    rated_power: float | None = None
    rotor_diameter: float | None = None
    hub_height: float | None = None
    num_blades: int | None = None
    cut_in_speed: float | None = None
    cut_out_speed: float | None = None
    rated_speed: float | None = None

    dt: float | None = None
    t_max: float | None = None

    platform_type: str
    water_depth: float | None = None

    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
