"""Component ORM models: Tower, Blade, Airfoil, Controller, TurbineModel."""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ---------------------------------------------------------------------------
# Tower
# ---------------------------------------------------------------------------
class Tower(Base):
    __tablename__ = "towers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Geometry
    tower_height: Mapped[float] = mapped_column(Float, nullable=False)
    tower_base_height: Mapped[float] = mapped_column(Float, default=10.0, nullable=False)

    # Damping ratios (% critical)
    tower_fa_damping_1: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    tower_fa_damping_2: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    tower_ss_damping_1: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    tower_ss_damping_2: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    # Distributed properties — array of station dicts
    # Each entry: {frac, mass_den, fa_stiff, ss_stiff, outer_diameter, wall_thickness}
    stations: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Mode shape polynomial coefficients (6 coefficients each, order 2-6)
    # Stored as JSON arrays instead of PostgreSQL ARRAY(Float)
    fa_mode_1_coeffs: Mapped[list | None] = mapped_column(JSON, nullable=True)
    fa_mode_2_coeffs: Mapped[list | None] = mapped_column(JSON, nullable=True)
    ss_mode_1_coeffs: Mapped[list | None] = mapped_column(JSON, nullable=True)
    ss_mode_2_coeffs: Mapped[list | None] = mapped_column(JSON, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # relationships
    project: Mapped["Project"] = relationship("Project", back_populates="towers")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Tower id={self.id} name={self.name!r} v{self.version}>"


# ---------------------------------------------------------------------------
# Blade
# ---------------------------------------------------------------------------
class Blade(Base):
    __tablename__ = "blades"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    blade_length: Mapped[float] = mapped_column(Float, nullable=False)

    # Structural stations — JSON array
    # Each: {frac, pitch_axis, struct_twist, mass_den, flap_stiff, edge_stiff}
    structural_stations: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Aerodynamic stations — JSON array
    # Each: {frac, chord, aero_twist, airfoil_id, aero_center}
    aero_stations: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Mode shape polynomial coefficients (stored as JSON arrays)
    flap_mode_1_coeffs: Mapped[list | None] = mapped_column(JSON, nullable=True)
    flap_mode_2_coeffs: Mapped[list | None] = mapped_column(JSON, nullable=True)
    edge_mode_1_coeffs: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Damping
    blade_flap_damping: Mapped[float] = mapped_column(Float, default=2.0, nullable=False)
    blade_edge_damping: Mapped[float] = mapped_column(Float, default=2.0, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # relationships
    project: Mapped["Project"] = relationship("Project", back_populates="blades")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Blade id={self.id} name={self.name!r} v{self.version}>"


# ---------------------------------------------------------------------------
# Airfoil
# ---------------------------------------------------------------------------
class Airfoil(Base):
    __tablename__ = "airfoils"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    family: Mapped[str | None] = mapped_column(String(100), nullable=True)  # e.g. "NACA", "DU"
    thickness_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Polar data — JSON array of {re, alpha[], cl[], cd[], cm[]}
    polars: Mapped[list | None] = mapped_column(JSON, nullable=True)

    source: Mapped[str | None] = mapped_column(Text, nullable=True)  # origin / reference
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # relationships
    organization: Mapped["Organization"] = relationship(  # noqa: F821
        "Organization", back_populates="airfoils"
    )

    def __repr__(self) -> str:
        return f"<Airfoil id={self.id} name={self.name!r}>"


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------
class ControllerType(str, enum.Enum):
    BASELINE = "baseline"
    ROSCO = "rosco"
    DISCON = "discon"
    CUSTOM = "custom"


class Controller(Base):
    __tablename__ = "controllers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    controller_type: Mapped[ControllerType] = mapped_column(
        Enum(ControllerType, name="controller_type", create_constraint=False, native_enum=False),
        default=ControllerType.BASELINE,
        nullable=False,
    )
    pcmode: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    vscontrl: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Arbitrary controller parameters stored as JSON
    parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    dll_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dll_procname: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # relationships
    project: Mapped["Project"] = relationship("Project", back_populates="controllers")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Controller id={self.id} name={self.name!r} v{self.version}>"


# ---------------------------------------------------------------------------
# TurbineModel — assembled turbine referencing tower, blade, controller
# ---------------------------------------------------------------------------
class TurbineModel(Base):
    __tablename__ = "turbine_models"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Component references
    tower_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("towers.id", ondelete="SET NULL"), nullable=True
    )
    blade_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("blades.id", ondelete="SET NULL"), nullable=True
    )
    controller_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("controllers.id", ondelete="SET NULL"), nullable=True
    )

    # Drivetrain
    gearbox_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    generator_inertia: Mapped[float | None] = mapped_column(Float, nullable=True)  # kg m^2
    drivetrain_stiffness: Mapped[float | None] = mapped_column(Float, nullable=True)  # N m/rad
    drivetrain_damping: Mapped[float | None] = mapped_column(Float, nullable=True)  # N m s/rad

    # Hub
    hub_mass: Mapped[float | None] = mapped_column(Float, nullable=True)  # kg
    hub_inertia: Mapped[float | None] = mapped_column(Float, nullable=True)  # kg m^2

    # Nacelle
    nacelle_mass: Mapped[float | None] = mapped_column(Float, nullable=True)  # kg
    nacelle_inertia: Mapped[float | None] = mapped_column(Float, nullable=True)  # kg m^2

    # Geometry
    overhang: Mapped[float | None] = mapped_column(Float, nullable=True)  # m
    shaft_tilt: Mapped[float | None] = mapped_column(Float, nullable=True)  # deg
    precone: Mapped[float | None] = mapped_column(Float, nullable=True)  # deg

    # Operating
    rotor_speed_rated: Mapped[float | None] = mapped_column(Float, nullable=True)  # rpm

    # DOF flags — JSON dict e.g. {"FlapDOF1": true, "EdgeDOF1": true, ...}
    dof_flags: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Offshore configuration (JSON blobs)
    substructure_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    hydrodyn_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    moordyn_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # relationships
    project: Mapped["Project"] = relationship(  # noqa: F821
        "Project", back_populates="turbine_models"
    )
    tower: Mapped["Tower"] = relationship("Tower", lazy="selectin")
    blade: Mapped["Blade"] = relationship("Blade", lazy="selectin")
    controller: Mapped["Controller"] = relationship("Controller", lazy="selectin")

    def __repr__(self) -> str:
        return f"<TurbineModel id={self.id} name={self.name!r} v{self.version}>"
