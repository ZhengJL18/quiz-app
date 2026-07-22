"""Admin vault management router — browse and manage user vault files.

All endpoints require admin/superadmin role.
Mounted at /api/v1/admin/vault
"""
import os
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.dependencies import require_admin
from app.db.engine import get_db
from app.db.models import User
from app.services.vault_manager import get_vault

router = APIRouter()


# ── Helpers ──


def _build_tree(directory: Path) -> list[dict]:
    """Recursively build a file/directory tree for a vault directory.

    Skips hidden files (leading dot) and .lock files, consistent with
    VaultManager.list_files behaviour.
    """
    entries = []
    try:
        for entry in sorted(directory.iterdir()):
            name = entry.name
            if name.startswith(".") or name.endswith(".lock"):
                continue
            if entry.is_dir():
                entries.append({
                    "name": name,
                    "type": "dir",
                    "children": _build_tree(entry),
                })
            else:
                st = entry.stat()
                entries.append({
                    "name": name,
                    "type": "file",
                    "size": st.st_size,
                    "modified": datetime.fromtimestamp(st.st_mtime).isoformat(),
                })
    except PermissionError:
        pass
    return entries


# ── Endpoints ──


@router.get("/users")
def list_users(
    db=Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """List all active users (id, username) for admin vault browsing."""
    users = db.query(User).filter(User.is_active == True).all()
    return [{"id": u.id, "username": u.username} for u in users]


@router.get("/{user_id}")
def list_vault(
    user_id: int,
    db=Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """List all files in a user's vault as a recursive tree."""
    user = db.query(User).filter_by(id=user_id, is_active=True).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    vault = get_vault(user_id)
    return {
        "root": str(vault.root),
        "tree": _build_tree(vault.root),
    }


@router.get("/{user_id}/file")
def read_vault_file(
    user_id: int,
    path: str = Query(..., description="Relative path within vault"),
    db=Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Read a file from a user's vault by relative path."""
    user = db.query(User).filter_by(id=user_id, is_active=True).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    vault = get_vault(user_id)
    content = vault.read(path)
    if content is None:
        raise HTTPException(status_code=404, detail="File not found")
    return {"path": path, "content": content}


@router.delete("/{user_id}/file", status_code=204)
def delete_vault_file(
    user_id: int,
    path: str = Query(..., description="Relative path within vault"),
    db=Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Delete a file from a user's vault by relative path.

    Only files (not directories) can be deleted through this endpoint.
    Path traversal outside the vault directory is rejected.
    """
    user = db.query(User).filter_by(id=user_id, is_active=True).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    vault = get_vault(user_id)
    full = (vault.root / path).resolve()

    # Path traversal guard (same pattern as VaultManager.read / write)
    if not str(full).startswith(str(vault.root.resolve())):
        raise HTTPException(status_code=400, detail="Path traversal detected")
    if not full.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if full.is_dir():
        raise HTTPException(status_code=400, detail="Cannot delete a directory; only files are supported")

    os.remove(full)
    return None


class FileUpdate(BaseModel):
    content: str


@router.put("/{user_id}/file")
def update_vault_file(
    user_id: int,
    body: FileUpdate,
    path: str = Query(..., description="Relative path within vault"),
    db=Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Update (write) a file in a user's vault."""

    user = db.query(User).filter_by(id=user_id, is_active=True).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    vault = get_vault(user_id)
    # Validate path is within vault
    full = (vault.root / path).resolve()
    if not str(full).startswith(str(vault.root.resolve())):
        raise HTTPException(status_code=400, detail="Path traversal detected")

    vault.write(path, body.content)
    return {"ok": True, "path": path}
