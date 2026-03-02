"""File browser endpoints for viewing generated OpenFAST input files."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.project import Project
from app.models.user import User

router = APIRouter(prefix="/projects/{project_id}/files", tags=["files"])


class FileNode(BaseModel):
    """A file or directory node in the project file tree."""
    name: str
    path: str  # relative to project root
    is_dir: bool
    size: int = 0
    children: list["FileNode"] | None = None


async def _verify_project_access(
    project_id: str, user: User, db: AsyncSession
) -> None:
    """Verify that the user's org owns the project."""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.org_id == user.org_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")


def _get_project_dir(project_id: str) -> Path:
    """Get the project files directory."""
    return Path(settings.PROJECTS_DIR) / str(project_id)


def _build_file_tree(root: Path, rel_base: Path | None = None) -> list[FileNode]:
    """Recursively build a file tree from a directory."""
    if rel_base is None:
        rel_base = root

    nodes: list[FileNode] = []
    if not root.exists():
        return nodes

    # Sort: directories first, then files, alphabetically
    entries = sorted(root.iterdir(), key=lambda e: (not e.is_dir(), e.name))

    for entry in entries:
        rel_path = str(entry.relative_to(rel_base))
        if entry.is_dir():
            children = _build_file_tree(entry, rel_base)
            nodes.append(FileNode(
                name=entry.name,
                path=rel_path,
                is_dir=True,
                children=children,
            ))
        else:
            nodes.append(FileNode(
                name=entry.name,
                path=rel_path,
                is_dir=False,
                size=entry.stat().st_size,
            ))

    return nodes


@router.get("", response_model=list[FileNode])
async def list_files(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all generated files for a project as a tree structure."""
    await _verify_project_access(project_id, current_user, db)
    project_dir = _get_project_dir(project_id)

    if not project_dir.exists():
        return []

    return _build_file_tree(project_dir)


@router.get("/content/{file_path:path}")
async def get_file_content(
    project_id: str,
    file_path: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the text content of a generated file."""
    await _verify_project_access(project_id, current_user, db)

    project_dir = _get_project_dir(project_id)
    full_path = project_dir / file_path

    # Security: ensure path doesn't escape project directory
    try:
        full_path = full_path.resolve()
        project_dir_resolved = project_dir.resolve()
        if not str(full_path).startswith(str(project_dir_resolved)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    except (OSError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path")

    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # Return text content for OpenFAST files
    try:
        content = full_path.read_text(encoding="utf-8")
        return PlainTextResponse(content)
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Binary file — use download endpoint",
        )


@router.get("/download/{file_path:path}")
async def download_file(
    project_id: str,
    file_path: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download a generated file."""
    await _verify_project_access(project_id, current_user, db)

    project_dir = _get_project_dir(project_id)
    full_path = project_dir / file_path

    # Security: ensure path doesn't escape project directory
    try:
        full_path = full_path.resolve()
        project_dir_resolved = project_dir.resolve()
        if not str(full_path).startswith(str(project_dir_resolved)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    except (OSError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path")

    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    return FileResponse(
        path=str(full_path),
        filename=full_path.name,
        media_type="application/octet-stream",
    )
