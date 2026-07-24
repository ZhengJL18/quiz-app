"""Questions router — list and detail endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.engine import get_db
from app.db.models import User, Question
from app.dependencies import get_current_user
from app.schemas.question import QuestionOut

router = APIRouter()


@router.get("", response_model=list[QuestionOut])
def list_questions(
    subject_id: int = Query(None),
    chapter_id: int = Query(None),
    question_type: str = Query(None),
    difficulty: int = Query(None, ge=1, le=5),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Question).join(Subject).filter(Subject.user_id == current_user.id)
    if subject_id:
        q = q.filter(Question.subject_id == subject_id)
    if chapter_id:
        q = q.filter(Question.chapter_id == chapter_id)
    if question_type:
        q = q.filter(Question.question_type == question_type)
    if difficulty:
        q = q.filter(Question.difficulty == difficulty)
    return q.limit(100).all()


@router.get("/{question_id}", response_model=QuestionOut)
def get_question(
    question_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    question = db.query(Question).filter_by(id=question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return question


@router.delete("/{question_id}", status_code=204)
def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    question = db.query(Question).filter_by(id=question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    db.delete(question)
    db.commit()
    return None
