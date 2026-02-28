"""Standalone entry point for WindForge API server.

Used by PyInstaller (desktop mode) and for direct execution.
"""

import os

import uvicorn

from app.main import app  # noqa: F401  — needed for uvicorn reference


def main():
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
