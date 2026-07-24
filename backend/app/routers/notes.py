"""Notes router — materials library + note editor + AI integration."""

import json
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.engine import get_db
from app.db.models import NoteMaterial, Note, User
from app.dependencies import get_current_user

router = APIRouter()


# ── Schemas ──

class MaterialCreate(BaseModel):
    content: str
    source_url: str = ""
    source_label: str = ""
    color_tag: str = "default"

class MaterialUpdate(BaseModel):
    content: str | None = None
    source_label: str | None = None
    color_tag: str | None = None
    order_index: int | None = None

class NoteCreate(BaseModel):
    title: str = "无标题笔记"
    content: str = ""
    subject_id: int | None = None

class NoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    is_pinned: bool | None = None

class AIWriteRequest(BaseModel):
    note_id: int
    instruction: str  # e.g. "根据素材库内容帮我整理成笔记"
    selected_material_ids: list[int] = []


# ── Materials Library ──

@router.get("/materials")
def list_materials(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all materials for the current user."""
    materials = db.query(NoteMaterial).filter_by(user_id=current_user.id).order_by(
        NoteMaterial.order_index, NoteMaterial.created_at.desc()
    ).all()
    return [
        {
            "id": m.id, "content": m.content, "source_url": m.source_url,
            "source_label": m.source_label, "color_tag": m.color_tag,
            "order_index": m.order_index, "created_at": m.created_at.isoformat(),
        }
        for m in materials
    ]


@router.post("/materials")
def create_material(
    body: MaterialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clip content into the material library."""
    max_order = db.query(func.max(NoteMaterial.order_index)).filter_by(
        user_id=current_user.id
    ).scalar() or 0
    mat = NoteMaterial(
        user_id=current_user.id,
        content=body.content,
        source_url=body.source_url,
        source_label=body.source_label,
        color_tag=body.color_tag,
        order_index=max_order + 1,
    )
    db.add(mat)
    db.commit()
    db.refresh(mat)
    return {"id": mat.id, "ok": True}


@router.put("/materials/{material_id}")
def update_material(
    material_id: int,
    body: MaterialUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a material (edit, reorder, recolor)."""
    mat = db.query(NoteMaterial).filter_by(id=material_id, user_id=current_user.id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")
    if body.content is not None: mat.content = body.content
    if body.source_label is not None: mat.source_label = body.source_label
    if body.color_tag is not None: mat.color_tag = body.color_tag
    if body.order_index is not None: mat.order_index = body.order_index
    db.commit()
    return {"ok": True}


@router.delete("/materials/{material_id}")
def delete_material(
    material_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a material."""
    mat = db.query(NoteMaterial).filter_by(id=material_id, user_id=current_user.id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")
    db.delete(mat)
    db.commit()
    return {"ok": True}


# ── Notes (vault-backed) ──

from app.services.vault_manager import get_vault

def _read_note(note: Note) -> str:
    """Read note content from vault if path pointer, else return legacy content."""
    c = (note.content or "").strip()
    if c.startswith("笔记/"):
        vault = get_vault(note.user_id)
        return vault.read(c) or ""
    return c

def _write_note(note: Note, content: str):
    """Write note content to vault, store pointer in DB."""
    vault = get_vault(note.user_id)
    vault_path = f"笔记/{note.id}.md"
    vault.write(vault_path, content)
    note.content = vault_path

def _note_json(n: Note) -> dict:
    return {
        "id": n.id, "title": n.title,
        "content": _read_note(n),
        "subject_id": n.subject_id, "is_pinned": n.is_pinned,
        "created_at": n.created_at.isoformat(), "updated_at": n.updated_at.isoformat(),
    }


@router.get("/{note_id}")
def get_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single note with full content from vault."""
    note = db.query(Note).filter_by(id=note_id, user_id=current_user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return _note_json(note)


@router.get("")
def list_notes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all notes. Content field returns vault content for preview."""
    notes = db.query(Note).filter_by(user_id=current_user.id).order_by(
        Note.is_pinned.desc(), Note.updated_at.desc()
    ).all()
    return [_note_json(n) for n in notes]


@router.post("")
def create_note(
    body: NoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new note. Writes to vault, stores path pointer."""
    note = Note(
        user_id=current_user.id, title=body.title,
        content="", subject_id=body.subject_id,
    )
    db.add(note)
    db.flush()
    if body.content:
        _write_note(note, body.content)
    else:
        note.content = f"笔记/{note.id}.md"
    db.commit()
    db.refresh(note)
    return {"id": note.id, "ok": True}


@router.put("/{note_id}")
def update_note(
    note_id: int,
    body: NoteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a note. Writes content to vault."""
    note = db.query(Note).filter_by(id=note_id, user_id=current_user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    if body.title is not None: note.title = body.title
    if body.content is not None: _write_note(note, body.content)
    if body.is_pinned is not None: note.is_pinned = body.is_pinned
    note.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


@router.delete("/{note_id}")
def delete_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a note and its vault file."""
    note = db.query(Note).filter_by(id=note_id, user_id=current_user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    # Remove vault file
    try:
        import os
        vault = get_vault(note.user_id)
        vault_path = f"笔记/{note.id}.md"
        full = vault.root / vault_path
        if full.exists():
            os.remove(full)
    except Exception:
        pass
    db.delete(note)
    db.commit()
    return {"ok": True}


# ── AI-powered note writing ──

@router.post("/ai-write")
async def ai_write_note(
    body: AIWriteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Let AI write/rewrite a note, optionally using selected materials as context."""
    note = db.query(Note).filter_by(id=body.note_id, user_id=current_user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    # Gather materials context
    materials_context = ""
    if body.selected_material_ids:
        mats = db.query(NoteMaterial).filter(
            NoteMaterial.id.in_(body.selected_material_ids),
            NoteMaterial.user_id == current_user.id,
        ).all()
        materials_context = "\n\n".join(
            f"【素材 {i+1}】{m.content}" for i, m in enumerate(mats)
        )

    async def event_stream():
        try:
            from app.ai_service.client import DeepSeekClient
            client = DeepSeekClient(api_key=current_user.api_key)
            current_content = _read_note(note)
            prompt = (
                f"你是一个笔记助手。用户正在编辑一篇笔记。\n\n"
                f"=== 当前笔记标题 ===\n{note.title}\n\n"
                f"=== 当前笔记内容 ===\n{current_content}\n\n"
            )
            if materials_context:
                prompt += f"=== 可用素材 ===\n{materials_context}\n\n"
            prompt += (
                f"=== 用户指令 ===\n{body.instruction}\n\n"
                f"请根据指令修改笔记内容。输出完整的修改后笔记（Markdown格式，支持LaTeX公式用$...$或$$...$$）。"
                f"保留用户原有内容中有价值的部分，整合素材库中的相关内容。"
            )
            messages = [{"role": "user", "content": prompt}]
            full = ""
            async for chunk in client.generate_stream(
                messages, temperature=0.5, max_tokens=4096, model="deepseek-chat"
            ):
                full += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                await asyncio.sleep(0.01)
            # Auto-save to vault
            _write_note(note, full)
            note.updated_at = datetime.now(timezone.utc)
            db.commit()
            yield f"data: {json.dumps({'done': True, 'saved': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
