"""WindForge API — FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from passlib.context import CryptContext
from sqlalchemy import select

from app.config import settings
from app.database import async_session_factory, create_tables, engine
from app.routers import auth, blades, controllers, files, frequency, hydro, metocean, modeshape, projects, reference_data, templates, towers, turbine_models, websocket, wind
from app.routers import fatigue as fatigue_router_mod
from app.routers import airfoil_tools as airfoil_tools_router_mod
from app.routers import bem as bem_router_mod
from app.routers import dynamics as dynamics_router_mod
from app.routers import stochastic as stochastic_router_mod
from app.routers import potentialflow as potentialflow_router_mod
from app.routers import particle as particle_router_mod
from app.routers.simulations import dlc_router, router as simulations_router

logger = logging.getLogger("windforge")
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def _seed_default_user():
    """Create default admin user and org on first launch (desktop mode)."""
    from app.models.user import Organization, User, UserRole

    async with async_session_factory() as session:
        result = await session.execute(select(User).limit(1))
        if result.scalar_one_or_none() is not None:
            return  # Users already exist

        logger.info("First launch — creating default admin user")
        org = Organization(name="WindForge Desktop")
        session.add(org)
        await session.flush()

        user = User(
            email="admin@windforge.app",
            hashed_password=_pwd_ctx.hash("windforge"),
            full_name="Admin",
            org_id=org.id,
            role=UserRole.ADMIN,
        )
        session.add(user)
        await session.commit()
        logger.info("Default user created: admin@windforge.app")


async def _seed_airfoils():
    """Seed airfoil polar data from reference files + generated FFA-W3 polars.

    Runs on every startup — skips if airfoils already exist.
    """
    from app.models.components import Airfoil
    from app.models.user import Organization
    from app.openfast.reference_parser import list_airfoils

    async with async_session_factory() as session:
        # Check if airfoils already exist
        result = await session.execute(select(Airfoil).limit(1))
        if result.scalar_one_or_none() is not None:
            return  # Already seeded

        # Get org_id
        result = await session.execute(select(Organization).limit(1))
        org = result.scalar_one_or_none()
        if org is None:
            return
        org_id = org.id

        count = 0

        # 1) Seed from NREL-5MW reference airfoil files
        try:
            ref_airfoils = list_airfoils("NREL-5MW")
            for af_data in ref_airfoils:
                name = af_data["name"]
                alpha = af_data.get("alpha", [])
                cl = af_data.get("cl", [])
                cd = af_data.get("cd", [])
                cm = af_data.get("cm", [])
                if not alpha or not cl or not cd:
                    continue

                # Determine family and thickness
                family = None
                thickness = None
                if "Cylinder" in name:
                    family = "Cylinder"
                    thickness = 1.0
                elif "DU" in name:
                    family = "DU"
                    # Extract thickness from name like DU21_A17 → 0.21
                    import re as _re
                    m = _re.search(r"DU(\d+)", name)
                    if m:
                        thickness = int(m.group(1)) / 100.0
                elif "NACA" in name:
                    family = "NACA"
                    thickness = 0.18

                airfoil = Airfoil(
                    org_id=org_id,
                    name=name,
                    family=family,
                    thickness_ratio=thickness,
                    polars=[{
                        "re": 1e6,
                        "alpha": alpha,
                        "cl": cl,
                        "cd": cd,
                        "cm": cm,
                    }],
                    source="NREL-5MW reference",
                )
                session.add(airfoil)
                count += 1
        except Exception as exc:
            logger.warning("Failed to seed NREL-5MW airfoils: %s", exc)

        # 2) Seed IEA-15MW FFA-W3 airfoils (generated from thickness-based NACA approximation)
        _ffa_airfoils = _generate_ffa_w3_polars()
        for af_data in _ffa_airfoils:
            airfoil = Airfoil(
                org_id=org_id,
                name=af_data["name"],
                family="FFA-W3",
                thickness_ratio=af_data["thickness"],
                polars=[{
                    "re": 1e6,
                    "alpha": af_data["alpha"],
                    "cl": af_data["cl"],
                    "cd": af_data["cd"],
                    "cm": af_data["cm"],
                }],
                source=af_data["source"],
            )
            session.add(airfoil)
            count += 1

        await session.commit()
        logger.info("Seeded %d airfoils with polar data", count)


def _generate_ffa_w3_polars() -> list[dict]:
    """Generate approximate polar data for FFA-W3 family airfoils.

    Uses welib's thin airfoil theory with thickness corrections.
    The FFA-W3-xxx naming means xxx/10 = thickness in %.
    """
    import numpy as np

    # FFA-W3 airfoils used by IEA-15MW reference blade
    ffa_specs = [
        {"name": "Cylinder", "thickness": 1.0, "source": "Cylinder (t/c=100%)"},
        {"name": "FFA_W3_600", "thickness": 0.60, "source": "FFA-W3-600 approx (t/c=60%)"},
        {"name": "FFA_W3_480", "thickness": 0.48, "source": "FFA-W3-480 approx (t/c=48%)"},
        {"name": "FFA_W3_360", "thickness": 0.36, "source": "FFA-W3-360 approx (t/c=36%)"},
        {"name": "FFA_W3_301", "thickness": 0.301, "source": "FFA-W3-301 approx (t/c=30.1%)"},
        {"name": "FFA_W3_241", "thickness": 0.241, "source": "FFA-W3-241 approx (t/c=24.1%)"},
        {"name": "FFA_W3_211", "thickness": 0.211, "source": "FFA-W3-211 approx (t/c=21.1%)"},
        {"name": "NACA_64_618", "thickness": 0.18, "source": "NACA 64-618 approx (t/c=18%)"},
    ]

    results = []
    for spec in ffa_specs:
        tc = spec["thickness"]
        alpha_deg = np.arange(-10.0, 30.5, 0.5).tolist()

        if tc >= 0.9:
            # Pure cylinder — zero lift, constant drag
            cl = [0.0] * len(alpha_deg)
            cd = [1.2] * len(alpha_deg)
            cm = [0.0] * len(alpha_deg)
        elif tc >= 0.5:
            # Thick transitional section — reduced lift, high drag
            cl_slope = 2 * np.pi * (1 - tc) * 0.6  # heavily reduced
            cd_min = 0.02 + 0.8 * tc  # high parasitic drag
            cl = []
            cd = []
            cm = []
            for a in alpha_deg:
                a_rad = np.radians(a)
                cl_val = cl_slope * a_rad
                # Stall around 8 degrees
                if abs(a) > 8:
                    cl_val = cl_val * np.exp(-0.05 * (abs(a) - 8) ** 2)
                cl.append(round(float(cl_val), 6))
                cd.append(round(float(cd_min + 0.005 * a_rad**2), 6))
                cm.append(round(float(-0.02 * a_rad), 6))
        else:
            # Standard thick airfoil — use thin airfoil theory with corrections
            cl_slope = 2 * np.pi * (1 + 0.77 * tc)  # thickness correction
            alpha_zl = -2.0 * tc * 10  # zero-lift angle shifts with camber
            cd_min = 0.006 + 0.15 * tc**2  # drag increases with thickness
            cl_max = 1.2 + 0.5 * (0.21 - tc) if tc < 0.30 else 0.8
            alpha_stall = 12.0 - 15 * tc  # stall earlier for thick airfoils

            cl = []
            cd = []
            cm = []
            for a in alpha_deg:
                a_eff = a - alpha_zl
                a_rad = np.radians(a_eff)
                cl_val = cl_slope * a_rad

                # Smooth stall model
                if a_eff > alpha_stall:
                    excess = a_eff - alpha_stall
                    cl_val = cl_max * np.exp(-0.08 * excess**1.5)
                elif a_eff < -alpha_stall:
                    excess = -a_eff - alpha_stall
                    cl_val = -cl_max * np.exp(-0.08 * excess**1.5)

                # Drag bucket + induced drag
                cd_val = cd_min + 0.01 * a_rad**2 + 0.005 * max(0, abs(a_eff) - 5) ** 2 * 0.001

                # Moment coefficient
                cm_val = -0.05 - 0.02 * a_rad

                cl.append(round(float(cl_val), 6))
                cd.append(round(float(cd_val), 6))
                cm.append(round(float(cm_val), 6))

        spec["alpha"] = alpha_deg
        spec["cl"] = cl
        spec["cd"] = cd
        spec["cm"] = cm
        results.append(spec)

    return results


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler — startup and shutdown logic."""

    # ---- startup ----
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )
    logger.info("WindForge API starting up")

    # Ensure the OpenFAST work directory exists
    work_dir = Path(settings.OPENFAST_WORK_DIR)
    work_dir.mkdir(parents=True, exist_ok=True)
    logger.info("OpenFAST work directory: %s", work_dir)

    projects_dir = Path(settings.PROJECTS_DIR)
    projects_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Projects directory: %s", projects_dir)

    # In desktop mode, create tables and seed default user
    if settings.DESKTOP_MODE:
        logger.info("Desktop mode enabled — using SQLite, auto-creating tables")
        # Import all models so Base.metadata knows about them
        import app.models.components  # noqa: F401
        import app.models.project  # noqa: F401
        import app.models.simulation  # noqa: F401
        import app.models.metocean  # noqa: F401
        import app.models.user  # noqa: F401

        await create_tables()
        await _seed_default_user()
        await _seed_airfoils()

    yield

    # ---- shutdown ----
    logger.info("WindForge API shutting down")
    await engine.dispose()


app = FastAPI(
    title="WindForge API",
    description="Wind turbine design platform powered by OpenFAST",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(towers.router, prefix="/api/v1")
app.include_router(blades.router, prefix="/api/v1")
app.include_router(controllers.router, prefix="/api/v1")
app.include_router(turbine_models.router, prefix="/api/v1")
app.include_router(simulations_router, prefix="/api/v1")
app.include_router(dlc_router, prefix="/api/v1")
app.include_router(websocket.router)
app.include_router(templates.router, prefix="/api/v1")
app.include_router(files.router, prefix="/api/v1")
app.include_router(metocean.router, prefix="/api/v1")
app.include_router(frequency.router, prefix="/api/v1")
app.include_router(modeshape.router, prefix="/api/v1")
app.include_router(hydro.router, prefix="/api/v1")
app.include_router(wind.router, prefix="/api/v1")
app.include_router(fatigue_router_mod.router, prefix="/api/v1")
app.include_router(airfoil_tools_router_mod.router, prefix="/api/v1")
app.include_router(reference_data.router, prefix="/api/v1")
app.include_router(bem_router_mod.router, prefix="/api/v1")
app.include_router(dynamics_router_mod.router, prefix="/api/v1")
app.include_router(stochastic_router_mod.router, prefix="/api/v1")
app.include_router(potentialflow_router_mod.router, prefix="/api/v1")
app.include_router(particle_router_mod.router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/", tags=["health"])
async def root():
    """Root health-check endpoint."""
    return {
        "service": "windforge-api",
        "status": "healthy",
        "version": "0.1.0",
    }


@app.get("/health", tags=["health"])
async def health():
    """Detailed health check."""
    return {
        "service": "windforge-api",
        "status": "healthy",
        "version": "0.1.0",
        "database": settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "sqlite",
        "openfast_lib": settings.OPENFAST_LIB_PATH,
    }


# ---------------------------------------------------------------------------
# Desktop mode config endpoint
# ---------------------------------------------------------------------------
@app.get("/api/v1/config", tags=["config"])
async def get_config():
    """Return app configuration for the frontend."""
    return {
        "desktop_mode": settings.DESKTOP_MODE,
        "version": "0.1.0",
    }
