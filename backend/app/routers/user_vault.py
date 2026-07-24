"""User vault file browser — self-serve, scoped to own files."""
import os
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.db.models import User
from app.dependencies import get_current_user
from app.services.vault_manager import get_vault

router = APIRouter()


def _build_tree(directory: Path) -> list[dict]:
    entries = []
    try:
        for entry in sorted(directory.iterdir()):
            name = entry.name
            if name.startswith(".") or name.endswith(".lock"):
                continue
            if entry.is_dir():
                entries.append({
                    "name": name, "type": "dir",
                    "children": _build_tree(entry),
                })
            else:
                st = entry.stat()
                entries.append({
                    "name": name, "type": "file",
                    "size": st.st_size,
                    "modified": datetime.fromtimestamp(st.st_mtime).isoformat(),
                })
    except PermissionError:
        pass
    return entries


@router.get("/tree")
def list_my_vault(current_user: User = Depends(get_current_user)):
    """List all files in the current user's vault as a tree."""
    vault = get_vault(current_user.id)
    return {"root": str(vault.root), "tree": _build_tree(vault.root)}


@router.get("/file")
def read_my_file(
    path: str = Query(..., description="Relative path within vault"),
    current_user: User = Depends(get_current_user),
):
    """Read a file from own vault."""
    vault = get_vault(current_user.id)
    content = vault.read(path)
    if content is None:
        raise HTTPException(status_code=404, detail="File not found")
    return {"path": path, "content": content}


class FileUpdate(BaseModel):
    content: str


@router.put("/file")
def write_my_file(
    body: FileUpdate,
    path: str = Query(..., description="Relative path within vault"),
    current_user: User = Depends(get_current_user),
):
    """Write/update a file in own vault."""
    vault = get_vault(current_user.id)
    full = (vault.root / path).resolve()
    if not str(full).startswith(str(vault.root.resolve())):
        raise HTTPException(status_code=400, detail="Path traversal detected")
    vault.write(path, body.content)
    return {"ok": True}


@router.delete("/file", status_code=204)
def delete_my_file(
    path: str = Query(..., description="Relative path within vault"),
    current_user: User = Depends(get_current_user),
):
    """Delete a file from own vault."""
    vault = get_vault(current_user.id)
    full = (vault.root / path).resolve()
    if not str(full).startswith(str(vault.root.resolve())):
        raise HTTPException(status_code=400, detail="Path traversal detected")
    if not full.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if full.is_dir():
        raise HTTPException(status_code=400, detail="Cannot delete directory")
    os.remove(full)
    return None
