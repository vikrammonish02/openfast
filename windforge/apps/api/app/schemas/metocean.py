"""Metocean site Pydantic schemas for API validation."""

from datetime import datetime

from pydantic import BaseModel, Field


class MetoceanSiteCreate(BaseModel):
    """Create a new metocean site."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    water_depth: float = Field(default=30.0, gt=0)
    current_speed: float = Field(default=0.0, ge=0)
    latitude: float | None = None
    longitude: float | None = None

    wind_speeds: list[float] | None = None
    wave_hs_nss: list[float] | None = None
    wave_tp_nss: list[float] | None = None
    wave_hs_sss: list[float] | None = None
    wave_tp_sss: list[float] | None = None
    wave_hs_ess: list[float] | None = None
    wave_tp_ess: list[float] | None = None
    wave_gamma: list[float] | None = None


class MetoceanSiteUpdate(BaseModel):
    """Update an existing metocean site (all fields optional)."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    water_depth: float | None = Field(None, gt=0)
    current_speed: float | None = Field(None, ge=0)
    latitude: float | None = None
    longitude: float | None = None

    wind_speeds: list[float] | None = None
    wave_hs_nss: list[float] | None = None
    wave_tp_nss: list[float] | None = None
    wave_hs_sss: list[float] | None = None
    wave_tp_sss: list[float] | None = None
    wave_hs_ess: list[float] | None = None
    wave_tp_ess: list[float] | None = None
    wave_gamma: list[float] | None = None


class MetoceanSiteResponse(BaseModel):
    """Metocean site response."""

    model_config = {"from_attributes": True}

    id: str
    org_id: str
    name: str
    description: str | None = None
    water_depth: float
    current_speed: float
    latitude: float | None = None
    longitude: float | None = None

    wind_speeds: list[float] | None = None
    wave_hs_nss: list[float] | None = None
    wave_tp_nss: list[float] | None = None
    wave_hs_sss: list[float] | None = None
    wave_tp_sss: list[float] | None = None
    wave_hs_ess: list[float] | None = None
    wave_tp_ess: list[float] | None = None
    wave_gamma: list[float] | None = None

    version: int
    is_active: bool
    created_at: datetime


class MetoceanAutoGenerate(BaseModel):
    """Request body to auto-generate metocean conditions from IEC 61400-3-1 formulas."""

    name: str = Field(default="IEC Auto-Generated", min_length=1, max_length=255)
    wind_speeds: list[float] = Field(
        default_factory=lambda: [4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0],
        description="Hub-height mean wind speeds (m/s)",
    )
    water_depth: float = Field(default=30.0, gt=0, description="Water depth (m)")
