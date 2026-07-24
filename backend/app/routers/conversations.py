"""Conversation history API — save/load AI chat conversations."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from app.dependencies import get_current_user
from app.db.models import User, Conversation, ChatMessage
from app.db.engine import SessionLocal

router = APIRouter()


# ── Schemas ──

class MessageIn(BaseModel):
    role: str  # user / assistant
    content: str

class ConvoIn(BaseModel):
    id: str  # frontend-generated ID
    title: str = "新对话"
    messages: list[MessageIn] = []

class ConvoOut(BaseModel):
    id: str
    title: str
    messages: list[MessageIn]
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


# ── Helpers ──

def _now():
    return datetime.now(timezone.utc)


def _get_convo_by_frontend_id(db, user_id: int, frontend_id: str) -> Optional[Conversation]:
    """Find a conversation by its frontend-generated ID stored in title field."""
    # We store the frontend ID as a reference. Since Conversation.id is auto-increment,
    # we use a convention: check if the conversation has a matching frontend_id.
    # We'll use the `id` field directly - frontend will use backend IDs after creation.
    return None  # We'll match by backend ID instead


# ── Routes ──

@router.get("", response_model=list[ConvoOut])
def list_conversations(user: User = Depends(get_current_user)):
    """Get all conversations for the current user, newest first."""
    db = SessionLocal()
    try:
        convos = (
            db.query(Conversation)
            .filter_by(user_id=user.id)
            .order_by(Conversation.updated_at.desc())
            .limit(30)
            .all()
        )
        result = []
        for c in convos:
            result.append(ConvoOut(
                id=str(c.id),
                title=c.title,
                messages=[MessageIn(role=m.role, content=m.content) for m in c.messages],
                created_at=c.created_at.isoformat() if c.created_at else "",
                updated_at=c.updated_at.isoformat() if c.updated_at else "",
            ))
        return result
    finally:
        db.close()


@router.post("", response_model=ConvoOut)
def save_conversation(payload: ConvoIn, user: User = Depends(get_current_user)):
    """Save or update a conversation. If conversation with this ID exists, replace messages."""
    db = SessionLocal()
    try:
        # Try to find existing by the frontend_id stored as backend int ID
        try:
            convo_id = int(payload.id)
        except (ValueError, TypeError):
            convo_id = 0

        convo = db.query(Conversation).filter_by(id=convo_id, user_id=user.id).first()

        if convo:
            # Update existing — delete old messages, insert new
            db.query(ChatMessage).filter_by(conversation_id=convo.id).delete()
            convo.title = payload.title
            convo.updated_at = _now()
        else:
            # Create new
            convo = Conversation(
                user_id=user.id,
                title=payload.title,
                created_at=_now(),
                updated_at=_now(),
            )
            db.add(convo)
            db.flush()

        # Insert messages
        for msg in payload.messages:
            db.add(ChatMessage(
                conversation_id=convo.id,
                role=msg.role,
                content=msg.content,
                created_at=_now(),
            ))

        db.commit()
        db.refresh(convo)

        # Sync to vault for file manager visibility
        try:
            from app.services.vault_manager import get_vault
            import json
            vault = get_vault(user.id)
            conv_json = {
                "id": convo.id,
                "title": convo.title,
                "messages": [{"role": m.role, "content": m.content} for m in convo.messages],
                "created_at": convo.created_at.isoformat() if convo.created_at else "",
                "updated_at": convo.updated_at.isoformat() if convo.updated_at else "",
            }
            vault.write(f"chat/{convo.id}.json", json.dumps(conv_json, ensure_ascii=False, indent=2))
        except Exception:
            pass  # vault sync is best-effort, don't fail the API call

        return ConvoOut(
            id=str(convo.id),
            title=convo.title,
            messages=[MessageIn(role=m.role, content=m.content) for m in convo.messages],
            created_at=convo.created_at.isoformat() if convo.created_at else "",
            updated_at=convo.updated_at.isoformat() if convo.updated_at else "",
        )
    finally:
        db.close()


@router.delete("/{convo_id}")
def delete_conversation(convo_id: int, user: User = Depends(get_current_user)):
    """Delete a conversation and all its messages."""
    db = SessionLocal()
    try:
        convo = db.query(Conversation).filter_by(id=convo_id, user_id=user.id).first()
        if not convo:
            raise HTTPException(status_code=404, detail="Conversation not found")
        db.delete(convo)
        db.commit()
        return {"ok": True}
    finally:
        db.close()
