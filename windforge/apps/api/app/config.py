"""Application configuration via environment variables with Pydantic Settings."""

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_db_url() -> str:
    """Return a platform-appropriate default SQLite database URL."""
    data_dir = Path.home() / "Library" / "Application Support" / "WindForge"
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite+aiosqlite:///{data_dir / 'windforge.db'}"


class Settings(BaseSettings):
    """WindForge API configuration.

    All values can be overridden via environment variables or a .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # --- Desktop mode ---
    DESKTOP_MODE: bool = True
    RESOURCES_PATH: str = ""  # Set by Electron to app's Resources dir

    # --- Database ---
    DATABASE_URL: str = _default_db_url()

    # --- Authentication / JWT ---
    SECRET_KEY: str = "CHANGE-ME-in-production-use-openssl-rand-hex-32"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # --- OpenFAST ---
    OPENFAST_LIB_PATH: str = "/usr/local/lib/libopenfastlib.so"
    OPENFAST_WORK_DIR: str = "/tmp/windforge/work"
    PROJECTS_DIR: str = "/tmp/windforge_projects"
    TURBSIM_EXE: str = "turbsim"
    OPENFAST_EXE: str = "openfast"
    ROSCO_LIB_PATH: str = ""

    # --- CORS ---
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    def resolve_binary_path(self, binary_setting: str) -> str:
        """Resolve a binary path relative to RESOURCES_PATH/bin/ if in desktop mode."""
        val = getattr(self, binary_setting)
        if self.RESOURCES_PATH and not os.path.isabs(val):
            candidate = os.path.join(self.RESOURCES_PATH, "bin", val)
            if os.path.isfile(candidate):
                return candidate
        return val


settings = Settings()
