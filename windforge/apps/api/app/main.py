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
from app.routers import auth, blades, controllers, files, projects, templates, towers, turbine_models, websocket
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
        import app.models.user  # noqa: F401

        await create_tables()
        await _seed_default_user()

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
