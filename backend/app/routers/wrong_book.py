"""Wrong-book / Collection router — manage bookmarked & wrong questions."""

import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.ai_service.generators import generate_explanation, generate_explanation_stream, generate_similar_question
from app.db.engine import get_db
from app.db.models import (
    Chapter,
    Question,
    Subject,
    User,
    WrongBook,
)
from app.dependencies import get_current_user
from app.schemas.question import QuestionOut
from app.schemas.wrong_book import WrongBookDetail, WrongBookOut, WrongBookUpdate

router = APIRouter()


@router.get("", response_model=list[WrongBookDetail])
def list_wrong_book(
    mastery_status: Optional[str] = Query(None),
    bookmarked: Optional[bool] = Query(True),  # default: only bookmarked
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List collection entries. Default: bookmarked=True (好题锦集)."""
    q = db.query(WrongBook).filter(WrongBook.user_id == current_user.id)
    if bookmarked is not None:
        q = q.filter(WrongBook.bookmarked == bookmarked)
    if mastery_status:
        q = q.filter(WrongBook.mastery_status == mastery_status)
    return q.order_by(WrongBook.last_wrong_at.desc()).all()


@router.get("/{wrong_book_id}", response_model=WrongBookDetail)
def get_wrong_entry(
    wrong_book_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single wrong book entry with full question details."""
    entry = db.query(WrongBook).filter_by(id=wrong_book_id, user_id=current_user.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Wrong book entry not found")
    return entry


@router.put("/{wrong_book_id}", response_model=WrongBookOut)
def update_wrong_entry(
    wrong_book_id: int,
    body: WrongBookUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update ai_explanation, user_note, or mastery_status."""
    entry = db.query(WrongBook).filter_by(id=wrong_book_id, user_id=current_user.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Wrong book entry not found")
    update_data = body.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(entry, key, val)
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/{wrong_book_id}/similar", response_model=QuestionOut)
async def generate_similar(
    wrong_book_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a similar question based on the wrong question."""
    entry = db.query(WrongBook).filter_by(id=wrong_book_id, user_id=current_user.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Wrong book entry not found")

    question = entry.question
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    subject = db.query(Subject).filter_by(id=question.subject_id).first()
    chapter = db.query(Chapter).filter_by(id=question.chapter_id).first()

    content = _parse_content_json(question)
    question_text = content.get("question_text", "")

    try:
        q_data = await generate_similar_question(
            question_text=question_text,
            question_type=question.question_type,
            subject_name=subject.name if subject else "",
            chapter_name=chapter.name if chapter else "",
            difficulty=question.difficulty,
            api_key=current_user.api_key,
        )
    except Exception as e:
        msg = str(e)
        if "balance" in msg.lower() or "insufficient" in msg.lower():
            raise HTTPException(status_code=402, detail="DeepSeek API 余额不足，请充值后重试。")
        if "required" in msg.lower() or "key" in msg.lower():
            raise HTTPException(status_code=400, detail="请先在账号设置中填入 DeepSeek API Key")
        raise HTTPException(status_code=500, detail=f"AI 生成失败：{msg[:200]}")

    new_question = Question(
        subject_id=question.subject_id,
        chapter_id=question.chapter_id,
        question_type=q_data.get("question_type", question.question_type),
        content_json=json.dumps(q_data.get("content_json", {}), ensure_ascii=False),
        difficulty=q_data.get("difficulty", question.difficulty),
        has_latex=q_data.get("has_latex", False),
        created_by="ai_generated",
        source_question_id=question.id,
    )
    db.add(new_question)
    db.commit()
    db.refresh(new_question)

    return QuestionOut.model_validate(new_question)


@router.post("/{wrong_book_id}/regenerate-explanation", response_model=WrongBookOut)
async def regenerate_explanation(
    wrong_book_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Regenerate AI explanation for a wrong book entry."""
    entry = db.query(WrongBook).filter_by(id=wrong_book_id, user_id=current_user.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Wrong book entry not found")

    question = entry.question
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    subject = db.query(Subject).filter_by(id=question.subject_id).first()
    content = _parse_content_json(question)
    question_text = content.get("question_text", "")
    correct_answer = content.get("correct_answer", "") or content.get("correct_answers", "")

    try:
        explanation = await generate_explanation(
            question_text=question_text,
            user_answer=entry.question.content_json,
            correct_answer=str(correct_answer),
            subject_name=subject.name if subject else "",
            options=content.get("options"),
            api_key=current_user.api_key,
        )
    except Exception as e:
        msg = str(e)
        if "balance" in msg.lower() or "insufficient" in msg.lower():
            raise HTTPException(status_code=402, detail="DeepSeek API 余额不足，请充值后重试。")
        if "required" in msg.lower() or "key" in msg.lower():
            raise HTTPException(status_code=400, detail="请先在账号设置中填入 DeepSeek API Key")
        raise HTTPException(status_code=500, detail=f"AI 生成失败：{msg[:200]}")

    entry.ai_explanation = explanation
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{wrong_book_id}", status_code=204)
def delete_wrong_entry(
    wrong_book_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a wrong book entry."""
    entry = db.query(WrongBook).filter_by(id=wrong_book_id, user_id=current_user.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Wrong book entry not found")
    # Cascade delete SRS schedule
    if entry.srs_schedule:
        db.delete(entry.srs_schedule)
    db.delete(entry)
    db.commit()
    return None


@router.post("/{wrong_book_id}/toggle-bookmark", response_model=WrongBookOut)
def toggle_bookmark(
    wrong_book_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle the bookmarked flag on a collection entry."""
    entry = db.query(WrongBook).filter_by(id=wrong_book_id, user_id=current_user.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    entry.bookmarked = not entry.bookmarked
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/bookmark", response_model=WrongBookOut)
def bookmark_question(
    question_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bookmark a question (for 好题锦集). Creates entry if not already in wrong_book."""
    question = db.query(Question).filter_by(id=question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # Check if already exists
    existing = db.query(WrongBook).filter_by(
        user_id=current_user.id, question_id=question_id
    ).first()
    if existing:
        existing.bookmarked = True
        db.commit()
        db.refresh(existing)
        return existing

    # Create new entry with bookmarked=True
    now = datetime.now(timezone.utc)
    entry = WrongBook(
        user_id=current_user.id,
        question_id=question_id,
        first_wrong_at=now,
        last_wrong_at=now,
        wrong_count=0,  # was not answered wrong — just bookmarked
        bookmarked=True,
        mastery_status="reviewing",
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/{wrong_book_id}/explanation-stream")
async def explanation_stream(
    wrong_book_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """SSE — stream AI explanation regeneration for a wrong-book entry."""
    entry = db.query(WrongBook).filter_by(id=wrong_book_id, user_id=current_user.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    question = entry.question
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    subject = db.query(Subject).filter_by(id=question.subject_id).first()
    content = _parse_content_json(question)
    question_text = content.get("question_text", "")
    correct_answer = str(content.get("correct_answer", "") or content.get("correct_answers", ""))

    async def event_stream():
        full = ""
        try:
            async for chunk in generate_explanation_stream(
                question_text=question_text,
                user_answer=str(entry.question.content_json),
                correct_answer=correct_answer,
                subject_name=subject.name if subject else "",
                options=content.get("options"),
                api_key=current_user.api_key,
            ):
                full += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                await asyncio.sleep(0.01)
            # Cache to DB
            entry.ai_explanation = full
            db.commit()
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _parse_content_json(question: Question) -> dict:
    if isinstance(question.content_json, dict):
        return question.content_json
    return json.loads(question.content_json)
