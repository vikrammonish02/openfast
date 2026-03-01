"""Metocean site ORM model — org-level reusable wind-wave correlation data."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MetoceanSite(Base):
    __tablename__ = "metocean_sites"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Site parameters
    water_depth: Mapped[float] = mapped_column(Float, default=30.0, nullable=False)
    current_speed: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Correlated wind-wave table — JSON arrays indexed by wind speed bin
    wind_speeds: Mapped[list | None] = mapped_column(JSON, nullable=True)
    wave_hs_nss: Mapped[list | None] = mapped_column(JSON, nullable=True)
    wave_tp_nss: Mapped[list | None] = mapped_column(JSON, nullable=True)
    wave_hs_sss: Mapped[list | None] = mapped_column(JSON, nullable=True)
    wave_tp_sss: Mapped[list | None] = mapped_column(JSON, nullable=True)
    wave_hs_ess: Mapped[list | None] = mapped_column(JSON, nullable=True)
    wave_tp_ess: Mapped[list | None] = mapped_column(JSON, nullable=True)
    wave_gamma: Mapped[list | None] = mapped_column(JSON, nullable=True)

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
