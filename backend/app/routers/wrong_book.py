"""Wrong-book router — manage incorrectly answered questions."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.ai_service.generators import generate_explanation, generate_similar_question
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


@router.get("", response_model=list[WrongBookOut])
def list_wrong_book(
    mastery_status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List wrong book entries, optionally filtered by mastery_status."""
    q = db.query(WrongBook)
    if mastery_status:
        q = q.filter(WrongBook.mastery_status == mastery_status)
    return q.order_by(WrongBook.last_wrong_at.desc()).all()


@router.get("/{wrong_book_id}", response_model=WrongBookDetail)
def get_wrong_entry(
    wrong_book_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get a single wrong book entry with full question details."""
    entry = db.query(WrongBook).filter_by(id=wrong_book_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Wrong book entry not found")
    return entry


@router.put("/{wrong_book_id}", response_model=WrongBookOut)
def update_wrong_entry(
    wrong_book_id: int,
    body: WrongBookUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Update ai_explanation, user_note, or mastery_status."""
    entry = db.query(WrongBook).filter_by(id=wrong_book_id).first()
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
    _user: User = Depends(get_current_user),
):
    """Generate a similar question based on the wrong question."""
    entry = db.query(WrongBook).filter_by(id=wrong_book_id).first()
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
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {e}")

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
    _user: User = Depends(get_current_user),
):
    """Regenerate AI explanation for a wrong book entry."""
    entry = db.query(WrongBook).filter_by(id=wrong_book_id).first()
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
            user_answer=entry.question.content_json,  # fallback
            correct_answer=str(correct_answer),
            subject_name=subject.name if subject else "",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {e}")

    entry.ai_explanation = explanation
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{wrong_book_id}", status_code=204)
def delete_wrong_entry(
    wrong_book_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Remove a wrong book entry."""
    entry = db.query(WrongBook).filter_by(id=wrong_book_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Wrong book entry not found")
    # Cascade delete SRS schedule
    if entry.srs_schedule:
        db.delete(entry.srs_schedule)
    db.delete(entry)
    db.commit()
    return None


def _parse_content_json(question: Question) -> dict:
    if isinstance(question.content_json, dict):
        return question.content_json
    return json.loads(question.content_json)
