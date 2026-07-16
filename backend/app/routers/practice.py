"""Practice router — pure practice and answer submission."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.ai_service.generators import generate_explanation
from app.db.engine import get_db
from app.db.models import (
    Chapter,
    PracticeSession,
    Question,
    QuestionAttempt,
    SRSSchedule,
    Subject,
    User,
    WrongBook,
)
from app.dependencies import get_current_user
from app.schemas.practice import (
    PurePracticeRequest,
    PurePracticeResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
    SessionOut,
    UpdateCurrentIndexRequest,
)
from app.schemas.question import QuestionOut
from app.services.mastery import recalculate_chapter_mastery
from app.services.scoring import grade_answer

router = APIRouter()


def _get_question_by_id(db: Session, question_id: int) -> Question | None:
    return db.query(Question).filter_by(id=question_id).first()


@router.post("/pure", response_model=PurePracticeResponse)
def pure_practice(
    body: PurePracticeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a pure practice session (no lesson content)."""
    subject = db.query(Subject).filter_by(id=body.subject_id, is_active=True).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    # Build question query
    q = db.query(Question).filter(Question.subject_id == body.subject_id)
    if body.chapter_id:
        q = q.filter(Question.chapter_id == body.chapter_id)

    questions = q.order_by(func.random()).limit(body.count).all()
    if not questions:
        raise HTTPException(status_code=404, detail="No questions found")

    # Create session
    question_ids = [q.id for q in questions]
    session = PracticeSession(
        mode="pure",
        subject_id=body.subject_id,
        chapter_id=body.chapter_id,
        questions_order=json.dumps(question_ids, ensure_ascii=False),
    )
    db.add(session)
    db.flush()

    # Create attempts
    for qid in question_ids:
        attempt = QuestionAttempt(
            session_id=session.id,
            question_id=qid,
            is_correct=None,
        )
        db.add(attempt)

    db.commit()
    db.refresh(session)

    return PurePracticeResponse(
        session_id=session.id,
        questions=[QuestionOut.model_validate(q) for q in questions],
    )


@router.post("/sessions/{session_id}/submit", response_model=SubmitAnswerResponse)
async def submit_answer(
    session_id: int,
    body: SubmitAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit an answer for a question in a practice session."""
    # 1. Find attempt
    attempt = (
        db.query(QuestionAttempt)
        .filter_by(session_id=session_id, question_id=body.question_id)
        .first()
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="Question attempt not found")

    # 2. Find session
    session = db.query(PracticeSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 3. Find question
    question = _get_question_by_id(db, body.question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # 4. Grade
    is_correct = grade_answer(question, body.user_answer)

    # 5. Update attempt
    attempt.user_answer = body.user_answer
    attempt.is_correct = is_correct
    attempt.time_spent_seconds = body.time_spent_seconds
    attempt.attempted_at = datetime.now(timezone.utc)
    db.flush()

    explanation = ""

    # 6. If wrong and objective, handle wrong book + SRS
    content = _parse_content_json(question)
    correct_answer_str = content.get("correct_answer", "") or content.get("correct_answers", "")

    if is_correct is False:
        # Upsert wrong book entry
        wrong_entry = db.query(WrongBook).filter_by(question_id=question.id).first()
        if wrong_entry:
            wrong_entry.last_wrong_at = datetime.now(timezone.utc)
            wrong_entry.wrong_count = (wrong_entry.wrong_count or 0) + 1
        else:
            wrong_entry = WrongBook(
                question_id=question.id,
                first_wrong_at=datetime.now(timezone.utc),
                last_wrong_at=datetime.now(timezone.utc),
                wrong_count=1,
                mastery_status="not_mastered",
            )
            db.add(wrong_entry)
            db.flush()

            # Create SRS schedule for new wrong book entry
            srs = SRSSchedule(
                wrong_book_id=wrong_entry.id,
                next_review_at=datetime.now(timezone.utc),
                interval_days=1.0,
                ease_factor=2.5,
                review_count=0,
            )
            db.add(srs)

        # Generate explanation for wrong answer
        try:
            question_text = content.get("question_text", "")
            explanation = await generate_explanation(
                question_text=question_text,
                user_answer=body.user_answer,
                correct_answer=str(correct_answer_str),
                subject_name=session.subject.name if hasattr(session, "subject") else "",
            )
            wrong_entry.ai_explanation = explanation
        except Exception:
            explanation = "无法生成解析，请稍后重试。"

    elif is_correct is True:
        explanation = "回答正确！"
    else:
        # Subjective question (is_correct is None) — no AI grading
        explanation = "主观题，请自行核对答案。"

    # 7. Recalculate chapter mastery
    chapter_id = session.chapter_id or question.chapter_id
    try:
        recalculate_chapter_mastery(db, current_user.id, chapter_id)
    except Exception:
        pass  # Non-critical — don't break the request

    # 8. Get next question
    next_question = None
    try:
        order = json.loads(session.questions_order)
        current_idx = order.index(body.question_id) if body.question_id in order else -1
        next_idx = current_idx + 1
        if 0 <= next_idx < len(order):
            next_id = order[next_idx]
            nq = _get_question_by_id(db, next_id)
            if nq:
                next_question = QuestionOut.model_validate(nq)
    except (json.JSONDecodeError, ValueError, IndexError):
        pass

    db.commit()

    return SubmitAnswerResponse(
        is_correct=is_correct,
        explanation=explanation,
        next_question=next_question,
    )


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get a practice session by ID, with full question data."""
    import json
    session = db.query(PracticeSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Load questions from questions_order
    question_ids = json.loads(session.questions_order or "[]")
    questions = db.query(Question).filter(Question.id.in_(question_ids)).all()
    # Preserve original order
    q_map = {q.id: q for q in questions}
    ordered = [q_map[qid] for qid in question_ids if qid in q_map]

    result = SessionOut.model_validate(session)
    result.questions = [QuestionOut.model_validate(q) for q in ordered]
    return result


@router.put("/sessions/{session_id}/current-index")
def update_current_index(
    session_id: int,
    body: UpdateCurrentIndexRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Save current question index progress."""
    session = db.query(PracticeSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.current_index = body.current_index
    db.commit()
    return {"status": "ok"}


def _parse_content_json(question: Question) -> dict:
    if isinstance(question.content_json, dict):
        return question.content_json
    return json.loads(question.content_json)
