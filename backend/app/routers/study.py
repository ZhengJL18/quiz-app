"""Study router — lesson-practice mode."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai_service.generators import generate_lesson_content, generate_questions
from app.db.engine import get_db
from app.db.models import (
    Chapter,
    PracticeSession,
    Question,
    QuestionAttempt,
    Subject,
    User,
)
from app.dependencies import get_current_user
from app.schemas.practice import LessonPracticeRequest, LessonPracticeResponse
from app.schemas.question import QuestionOut

router = APIRouter()


@router.post("/lesson-practice", response_model=LessonPracticeResponse)
async def lesson_practice(
    body: LessonPracticeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a lesson-practice session for a leaf chapter."""
    # 1. Find chapter (must be a leaf)
    chapter = db.query(Chapter).filter_by(id=body.chapter_id, is_leaf=True).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found or not a leaf chapter")

    subject = db.query(Subject).filter_by(id=chapter.subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    # 2. Get or generate lesson content
    lesson_content = chapter.description or ""
    if not lesson_content:
        try:
            lesson_content = await generate_lesson_content(
                chapter_name=chapter.name,
                subject_name=subject.name,
            )
        except Exception:
            lesson_content = f"# {chapter.name}\n\n学习内容生成失败，请稍后重试。"

    # 3. Find existing questions for this chapter
    existing_qs = (
        db.query(Question)
        .filter(Question.chapter_id == chapter.id)
        .all()
    )
    existing_count = len(existing_qs)

    # 4. Generate more questions if needed
    all_questions = list(existing_qs)
    if existing_count < body.question_count:
        needed = body.question_count - existing_count
        try:
            generated = await generate_questions(
                subject_name=subject.name,
                chapter_name=chapter.name,
                count=needed,
                difficulty_range=(1, 5),
            )
            for q_data in generated:
                question = Question(
                    subject_id=subject.id,
                    chapter_id=chapter.id,
                    question_type=q_data.get("question_type", "single_choice"),
                    content_json=json.dumps(q_data.get("content_json", {}), ensure_ascii=False),
                    difficulty=q_data.get("difficulty", 1),
                    has_latex=q_data.get("has_latex", False),
                    created_by="ai_generated",
                )
                db.add(question)
                db.flush()
                all_questions.append(question)
        except Exception:
            # If AI generation fails, continue with existing questions
            pass

    # 5. Create PracticeSession
    question_ids = [q.id for q in all_questions]
    session = PracticeSession(
        mode="lesson",
        subject_id=subject.id,
        chapter_id=chapter.id,
        questions_order=json.dumps(question_ids, ensure_ascii=False),
        lesson_content=lesson_content,
    )
    db.add(session)
    db.flush()

    # 6. Create QuestionAttempt rows (is_correct = NULL = not yet answered)
    for qid in question_ids:
        attempt = QuestionAttempt(
            session_id=session.id,
            question_id=qid,
            is_correct=None,
        )
        db.add(attempt)

    db.commit()
    db.refresh(session)

    return LessonPracticeResponse(
        session_id=session.id,
        lesson_content=lesson_content or "",
        questions=[QuestionOut.model_validate(q) for q in all_questions],
        total_count=len(all_questions),
    )
