"""Frequency analysis Pydantic schemas for API validation."""

from pydantic import BaseModel, Field


class FrequencyRequest(BaseModel):
    """Request body for natural frequency computation."""

    turbine_model_id: str
    stage: str = Field(
        default="tower_rna",
        description=(
            "Configuration stage: blade_alone, tower_alone, tower_rna, "
            "monopile_alone, monopile_tower, full_operation, "
            "transport_blade, transport_tower, installation"
        ),
    )
    rotor_speed_rpm: float = Field(default=0.0, ge=0)


class FrequencyResponse(BaseModel):
    """Response with computed natural frequencies."""

    stage: str
    stage_label: str = ""
    rotor_speed_rpm: float = 0.0
    frequencies_hz: list[float]
    mode_descriptions: list[str]
    component_info: dict = Field(default_factory=dict)


class CampbellMode(BaseModel):
    """A single structural mode tracked across RPM values."""

    name: str
    frequencies: list[float]
    component: str  # "blade", "tower", "drivetrain"


class ExcitationLine(BaseModel):
    """An nP excitation line for Campbell diagrams."""

    rpm: list[float]
    freq: list[float]
    label: str


class CampbellRequest(BaseModel):
    """Request body for Campbell diagram computation."""

    turbine_model_id: str
    rpm_min: float = Field(default=0.0, ge=0)
    rpm_max: float = Field(default=15.0, gt=0)
    rpm_steps: int = Field(default=30, ge=5, le=200)
    n_modes: int = Field(default=10, ge=2, le=30)


class CampbellResponse(BaseModel):
    """Full Campbell diagram data for frontend plotting."""

    rpm_values: list[float]
    modes: list[CampbellMode]
    excitation_lines: dict[str, ExcitationLine]


class StageResult(BaseModel):
    """Frequency results for a single stage."""

    stage: str
    stage_label: str
    frequencies_hz: list[float]
    mode_descriptions: list[str]


class MultiStageRequest(BaseModel):
    """Request to compute frequencies at multiple project stages."""

    turbine_model_id: str
    stages: list[str] = Field(
        default_factory=lambda: ["tower_alone", "tower_rna", "full_operation"],
        description="List of stage identifiers to compute.",
    )
    rotor_speed_rpm: float = Field(default=0.0, ge=0)


class MultiStageResponse(BaseModel):
    """Bar chart data: frequencies grouped by stage."""

    stages: list[StageResult]
