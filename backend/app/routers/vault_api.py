"""Vault API — content endpoints reading from MD files instead of SQLite.

Replaces subjects.py + chapters.py + questions.py for content queries.
Practice, SRS, mastery, wrong_book still use SQLite.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from app.dependencies import get_current_user
from app.db.models import User
from app.vault import manager as vault

router = APIRouter()


# ── Schemas ──

class VaultSubjectOut(BaseModel):
    id: int
    name: str
    description: str = ""
    prompt_style: str = ""
    is_active: bool = True
    order_index: int = 99
    vault_path: str = ""

    model_config = {"extra": "allow"}


class VaultSubjectCreate(BaseModel):
    name: str
    description: str = ""
    prompt_style: str = ""


class VaultChapterOut(BaseModel):
    id: int
    name: str
    level: int = 1
    is_leaf: bool = False
    vault_path: str = ""
    question_count: int = 0
    lesson_content: str = ""
    children: list["VaultChapterOut"] = []

    model_config = {"extra": "allow"}


class VaultChapterCreate(BaseModel):
    subject_name: str
    name: str
    level: int = 3
    parent_path: str = ""
    is_leaf: bool = True


class VaultLessonOut(BaseModel):
    name: str
    lesson_content: str
    meta: dict = {}


# ── Subjects ──

@router.get("/subjects", response_model=list[VaultSubjectOut])
def list_subjects(current_user: User = Depends(get_current_user)):
    return vault.list_subjects()


@router.post("/subjects", response_model=VaultSubjectOut)
def create_subject(body: VaultSubjectCreate, current_user: User = Depends(get_current_user)):
    folder = vault.ensure_subject(body.name, body.description, body.prompt_style)
    return {"id": hash(body.name) % 100000, "name": body.name, "description": body.description,
            "prompt_style": body.prompt_style, "vault_path": str(folder.relative_to(vault.VAULT_ROOT)),
            "order_index": 99, "is_active": True}


@router.delete("/subjects/{name}", status_code=204)
def delete_subject(name: str, current_user: User = Depends(get_current_user)):
    if not vault.delete_subject(name):
        raise HTTPException(status_code=404, detail="Subject not found")
    return None


@router.put("/subjects/{name}")
def rename_subject(name: str, new_name: str = Query(...), current_user: User = Depends(get_current_user)):
    if not vault.rename_subject(name, new_name):
        raise HTTPException(status_code=404, detail="Subject not found or new name exists")
    return {"status": "ok"}


# ── Chapters ──

@router.get("/subjects/{subject_name}/chapters", response_model=list[VaultChapterOut])
def list_chapters(subject_name: str, current_user: User = Depends(get_current_user)):
    return vault.list_chapters(subject_name)


@router.post("/chapters", response_model=VaultChapterOut)
def create_chapter(body: VaultChapterCreate, current_user: User = Depends(get_current_user)):
    result = vault.ensure_chapter(body.subject_name, body.name, body.level,
                                   body.parent_path, body.is_leaf)
    return {"id": hash(str(result)) % 100000, "name": body.name, "level": body.level,
            "is_leaf": body.is_leaf, "vault_path": str(result.relative_to(vault.VAULT_ROOT / body.subject_name)),
            "children": [], "question_count": 0}


@router.delete("/chapters/{subject_name}", status_code=204)
def delete_chapter(subject_name: str, name: str = Query(...), parent_path: str = Query(""),
                   current_user: User = Depends(get_current_user)):
    if not vault.delete_chapter(subject_name, name, parent_path):
        raise HTTPException(status_code=404, detail="Chapter not found")
    return None


@router.put("/chapters/{subject_name}")
def update_chapter(subject_name: str, name: str = Query(...), new_name: str = Query(None),
                   parent_path: str = Query(""), current_user: User = Depends(get_current_user)):
    """Rename a chapter by deleting old and creating new."""
    if not new_name:
        raise HTTPException(status_code=400, detail="new_name required")
    meta, body = vault.get_lesson(subject_name, name, parent_path)
    if not meta:
        raise HTTPException(status_code=404, detail="Chapter not found")
    vault.delete_chapter(subject_name, name, parent_path)
    vault.ensure_chapter(subject_name, new_name, meta.get("level", 3), parent_path, meta.get("is_leaf", True))
    if body:
        vault.update_lesson_content(subject_name, new_name, body, parent_path)
    return {"status": "ok"}


# ── Lessons ──

@router.get("/lessons/{subject_name}", response_model=VaultLessonOut)
def get_lesson(subject_name: str, lesson_name: str = Query(...), parent_path: str = Query(""),
               current_user: User = Depends(get_current_user)):
    meta, body = vault.get_lesson(subject_name, lesson_name, parent_path)
    if not meta:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return {"name": meta.get("name", lesson_name), "lesson_content": body, "meta": meta}


@router.put("/lessons/{subject_name}")
def update_lesson(subject_name: str, lesson_name: str = Query(...), content: str = Query(""),
                  parent_path: str = Query(""), current_user: User = Depends(get_current_user)):
    if not vault.update_lesson_content(subject_name, lesson_name, content, parent_path):
        raise HTTPException(status_code=404, detail="Lesson not found")
    return {"status": "ok"}
