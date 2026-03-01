"""Simulation-related ORM models: DLC definitions, runs, cases, and results."""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ---------------------------------------------------------------------------
# DLC Definition
# ---------------------------------------------------------------------------
class DLCStatus(str, enum.Enum):
    DRAFT = "draft"
    READY = "ready"
    LOCKED = "locked"


class DLCDefinition(Base):
    __tablename__ = "dlc_definitions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    turbine_model_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("turbine_models.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # DLC case matrix — JSON array of case specifications
    # Each: {dlc_number, wind_speeds[], seeds, yaw_misalignments[], ...}
    dlc_cases: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # TurbSim configuration
    turbsim_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # WEIS metocean conditions — correlated wind-wave table
    metocean_conditions: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    total_case_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[DLCStatus] = mapped_column(
        Enum(DLCStatus, name="dlc_status", create_constraint=False, native_enum=False),
        default=DLCStatus.DRAFT,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # relationships
    project: Mapped["Project"] = relationship("Project")  # noqa: F821
    turbine_model: Mapped["TurbineModel"] = relationship("TurbineModel", lazy="selectin")  # noqa: F821
    simulations: Mapped[list["Simulation"]] = relationship(
        "Simulation", back_populates="dlc_definition", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<DLCDefinition id={self.id} name={self.name!r}>"


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------
class SimulationStatus(str, enum.Enum):
    PENDING = "pending"
    GENERATING_WIND = "generating_wind"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Simulation(Base):
    __tablename__ = "simulations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    dlc_definition_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("dlc_definitions.id", ondelete="CASCADE"), nullable=False
    )
    turbine_model_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("turbine_models.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[SimulationStatus] = mapped_column(
        Enum(SimulationStatus, name="simulation_status", create_constraint=False, native_enum=False),
        default=SimulationStatus.PENDING,
        nullable=False,
    )
    total_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    agent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # relationships
    project: Mapped["Project"] = relationship("Project", back_populates="simulations")  # noqa: F821
    dlc_definition: Mapped["DLCDefinition"] = relationship(
        "DLCDefinition", back_populates="simulations"
    )
    turbine_model: Mapped["TurbineModel"] = relationship("TurbineModel", lazy="selectin")  # noqa: F821
    cases: Mapped[list["SimulationCase"]] = relationship(
        "SimulationCase", back_populates="simulation", cascade="all, delete-orphan", lazy="selectin"
    )
    results_statistics: Mapped[list["ResultsStatistics"]] = relationship(
        "ResultsStatistics", back_populates="simulation", cascade="all, delete-orphan"
    )
    results_del: Mapped[list["ResultsDEL"]] = relationship(
        "ResultsDEL", back_populates="simulation", cascade="all, delete-orphan"
    )
    results_extreme: Mapped[list["ResultsExtreme"]] = relationship(
        "ResultsExtreme", back_populates="simulation", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Simulation id={self.id} name={self.name!r} status={self.status}>"


# ---------------------------------------------------------------------------
# SimulationCase
# ---------------------------------------------------------------------------
class CaseStatus(str, enum.Enum):
    PENDING = "pending"
    GENERATING_WIND = "generating_wind"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SimulationCase(Base):
    __tablename__ = "simulation_cases"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    simulation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False
    )
    dlc_number: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "1.1", "1.3"
    wind_speed: Mapped[float] = mapped_column(Float, nullable=False)  # m/s
    seed_number: Mapped[int] = mapped_column(Integer, nullable=False)
    yaw_misalignment: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # deg

    # --- WEIS-enhanced per-case fields ---
    wave_hs: Mapped[float | None] = mapped_column(Float, nullable=True)  # m
    wave_tp: Mapped[float | None] = mapped_column(Float, nullable=True)  # s
    wave_dir: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)  # deg
    wave_seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wave_gamma: Mapped[float | None] = mapped_column(Float, nullable=True)
    iec_wind_type: Mapped[str | None] = mapped_column(String(20), nullable=True, default="NTM")
    wind_profile_type: Mapped[str | None] = mapped_column(String(10), nullable=True, default="IEC")
    azimuth_deg: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    probability_weight: Mapped[float | None] = mapped_column(Float, nullable=True, default=1.0)
    initial_rotor_speed: Mapped[float | None] = mapped_column(Float, nullable=True)  # rpm
    initial_blade_pitch: Mapped[float | None] = mapped_column(Float, nullable=True)  # deg
    shutdown_time: Mapped[float | None] = mapped_column(Float, nullable=True)  # s
    analysis_type: Mapped[str | None] = mapped_column(String(20), nullable=True, default="ultimate")

    wind_field_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    input_files: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    status: Mapped[CaseStatus] = mapped_column(
        Enum(CaseStatus, name="case_status", create_constraint=False, native_enum=False),
        default=CaseStatus.PENDING,
        nullable=False,
    )
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    current_time: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # s
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    wall_time_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # relationships
    simulation: Mapped["Simulation"] = relationship("Simulation", back_populates="cases")
    results_statistics: Mapped[list["ResultsStatistics"]] = relationship(
        "ResultsStatistics", back_populates="simulation_case", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<SimulationCase id={self.id} dlc={self.dlc_number} "
            f"ws={self.wind_speed} seed={self.seed_number}>"
        )


# ---------------------------------------------------------------------------
# Results — Statistics per case
# ---------------------------------------------------------------------------
class ResultsStatistics(Base):
    __tablename__ = "results_statistics"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    simulation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False
    )
    simulation_case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("simulation_cases.id", ondelete="CASCADE"), nullable=False
    )
    dlc_number: Mapped[str] = mapped_column(String(20), nullable=False)
    wind_speed: Mapped[float] = mapped_column(Float, nullable=False)

    # Per-channel stats: {channel_name: {min, max, mean, std, ...}}
    channel_statistics: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # relationships
    simulation: Mapped["Simulation"] = relationship(
        "Simulation", back_populates="results_statistics"
    )
    simulation_case: Mapped["SimulationCase"] = relationship(
        "SimulationCase", back_populates="results_statistics"
    )

    def __repr__(self) -> str:
        return f"<ResultsStatistics id={self.id} case={self.simulation_case_id}>"


# ---------------------------------------------------------------------------
# Results — Damage Equivalent Loads (aggregated per simulation)
# ---------------------------------------------------------------------------
class ResultsDEL(Base):
    __tablename__ = "results_del"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    simulation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False
    )

    # DEL results: {channel_name: {del_value, ...}, ...}
    del_results: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    m_exponent: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)
    n_equivalent: Mapped[float] = mapped_column(Float, nullable=False, default=1e7)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # relationships
    simulation: Mapped["Simulation"] = relationship("Simulation", back_populates="results_del")

    def __repr__(self) -> str:
        return f"<ResultsDEL id={self.id} sim={self.simulation_id}>"


# ---------------------------------------------------------------------------
# Results — Extreme loads (aggregated per simulation)
# ---------------------------------------------------------------------------
class ResultsExtreme(Base):
    __tablename__ = "results_extreme"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    simulation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False
    )

    # Extreme load results: {channel: {max, min, associated_values...}, ...}
    extreme_loads: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # relationships
    simulation: Mapped["Simulation"] = relationship(
        "Simulation", back_populates="results_extreme"
    )

    def __repr__(self) -> str:
        return f"<ResultsExtreme id={self.id} sim={self.simulation_id}>"
