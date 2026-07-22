"""Practice router — pure practice and answer submission."""

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.ai_service.generators import generate_explanation, generate_explanation_stream
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


@router.post("/exam", response_model=PurePracticeResponse)
def exam_practice(
    body: PurePracticeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start an exam-style session: random questions from one or all subjects."""
    q = db.query(Question)
    if body.subject_id:
        q = q.filter(Question.subject_id == body.subject_id)
    if body.chapter_id:
        q = q.filter(Question.chapter_id == body.chapter_id)

    questions = q.order_by(func.random()).limit(body.count or 20).all()
    if not questions:
        raise HTTPException(status_code=404, detail="No questions found")

    question_ids = [q.id for q in questions]
    session = PracticeSession(
        mode="exam",
        subject_id=body.subject_id,
        chapter_id=body.chapter_id,
        user_id=_user.id,
        questions_order=json.dumps(question_ids, ensure_ascii=False),
    )
    db.add(session)
    db.flush()

    for qid in question_ids:
        db.add(QuestionAttempt(session_id=session.id, question_id=qid, is_correct=None))

    db.commit()
    db.refresh(session)
    return PurePracticeResponse(
        session_id=session.id,
        questions=[QuestionOut.model_validate(q) for q in questions],
    )


@router.post("/pure", response_model=PurePracticeResponse)
async def pure_practice(
    body: PurePracticeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a pure practice session — AI generates 3 fresh questions, never repeat."""
    subject = db.query(Subject).filter_by(id=body.subject_id, is_active=True).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    # If explicit question IDs provided, use those directly (e.g., from similar question generation)
    if body.question_ids:
        questions = db.query(Question).filter(
            Question.id.in_(body.question_ids),
            Question.subject_id == body.subject_id,
        ).all()
        if not questions:
            raise HTTPException(status_code=404, detail="Questions not found")
        question_ids = [q.id for q in questions]
        session = PracticeSession(
            mode="pure", subject_id=body.subject_id, chapter_id=body.chapter_id,
            user_id=_user.id,
            questions_order=json.dumps(question_ids, ensure_ascii=False),
        )
        db.add(session); db.flush()
        for qid in question_ids:
            db.add(QuestionAttempt(session_id=session.id, question_id=qid, is_correct=None))
        db.commit(); db.refresh(session)
        return PurePracticeResponse(
            session_id=session.id,
            questions=[QuestionOut.model_validate(q) for q in questions],
        )

    chapter = None
    if body.chapter_id:
        chapter = db.query(Chapter).filter_by(id=body.chapter_id, subject_id=subject.id).first()
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")

    count = body.count or 3

    # Adaptive difficulty hint
    from app.services.adaptive_difficulty import get_adaptive_prompt_hint
    from app.services.vault_manager import get_vault
    vault = get_vault(current_user.id)
    ch_name = chapter.name if chapter else subject.name
    diff_hint = get_adaptive_prompt_hint(vault, ch_name)
    full_prompt_style = (subject.prompt_style or "") + "\n" + diff_hint

    # AI-generate fresh questions for this chapter
    from app.ai_service.generators import generate_questions
    try:
        generated = await generate_questions(
            subject_name=subject.name,
            chapter_name=ch_name,
            count=count,
            difficulty_range=(1, 5),
            prompt_style=full_prompt_style,
            api_key=current_user.api_key,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI question generation failed: {str(e)[:200]}")

    # Save generated questions to DB
    saved_questions = []
    for q_data in generated:
        q = Question(
            subject_id=subject.id,
            chapter_id=chapter.id if chapter else 0,
            question_type=q_data.get("question_type", "single_choice"),
            content_json=json.dumps(q_data.get("content_json", {}), ensure_ascii=False),
            difficulty=q_data.get("difficulty", 1),
            has_latex=q_data.get("has_latex", False),
            created_by="ai_practice",
        )
        db.add(q)
        db.flush()
        saved_questions.append(q)

    # Create session
    question_ids = [q.id for q in saved_questions]
    session = PracticeSession(
        mode="pure",
        subject_id=body.subject_id,
        chapter_id=body.chapter_id,
        user_id=_user.id,
        questions_order=json.dumps(question_ids, ensure_ascii=False),
    )
    db.add(session)
    db.flush()

    for qid in question_ids:
        db.add(QuestionAttempt(session_id=session.id, question_id=qid, is_correct=None))

    db.commit()
    db.refresh(session)

    return PurePracticeResponse(
        session_id=session.id,
        questions=[QuestionOut.model_validate(q) for q in saved_questions],
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
    session = db.query(PracticeSession).filter_by(id=session_id, user_id=_user.id).first()
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
    grading_mode = "auto"

    # 6. Handle result based on grading type
    content = _parse_content_json(question)
    correct_answer_str = str(content.get("correct_answer", "") or content.get("correct_answers", ""))

    if is_correct is False:
        # Wrong objective answer — add to wrong book + SRS
        wrong_entry = db.query(WrongBook).filter_by(question_id=question.id, user_id=_user.id).first()
        if wrong_entry:
            wrong_entry.last_wrong_at = datetime.now(timezone.utc)
            wrong_entry.wrong_count = (wrong_entry.wrong_count or 0) + 1
        else:
            wrong_entry = WrongBook(
                user_id=_user.id, question_id=question.id,
                first_wrong_at=datetime.now(timezone.utc), last_wrong_at=datetime.now(timezone.utc),
                wrong_count=1, mastery_status="not_mastered",
            )
            db.add(wrong_entry)
            db.flush()
            srs = SRSSchedule(
                wrong_book_id=wrong_entry.id, next_review_at=datetime.now(timezone.utc),
                interval_days=1.0, ease_factor=2.5, review_count=0,
            )
            db.add(srs)

        # Generate explanation — reuse cached if available
        if wrong_entry and wrong_entry.ai_explanation:
            explanation = wrong_entry.ai_explanation
        else:
            try:
                explanation = await generate_explanation(
                    question_text=content.get("question_text", ""),
                    user_answer=body.user_answer,
                    correct_answer=correct_answer_str,
                    subject_name=session.subject.name if hasattr(session, "subject") else "",
                    options=content.get("options"),
                    api_key=current_user.api_key,
                )
                if wrong_entry:
                    wrong_entry.ai_explanation = explanation
            except Exception as exc:
                msg = str(exc)
                if "balance" in msg.lower() or "insufficient" in msg.lower():
                    explanation = "> ⚠️ DeepSeek API 余额不足，无法生成解析。请充值后重试。"
                elif "authentication" in msg.lower() or "401" in msg or "403" in msg:
                    explanation = "> ⚠️ API 密钥无效，请在个人设置中检查 DeepSeek API Key。"
                elif "required" in msg.lower():
                    explanation = "> ⚠️ 请先在个人设置中填入 DeepSeek API Key。"
                else:
                    explanation = f"> ❌ 解析生成失败：{msg[:150]}"

    elif is_correct is True:
        explanation = "回答正确！"
    else:
        # Subjective question (fill_blank, short_answer, calculation, proof)
        # User will self-judge after streaming explanation
        grading_mode = "self"
        explanation = ""  # Frontend will call streaming endpoint

    # 7. Recalculate chapter mastery
    chapter_id = session.chapter_id or question.chapter_id
    try:
        recalculate_chapter_mastery(db, current_user.id, chapter_id)
    except Exception as e:
        import logging
        logging.getLogger("uvicorn.error").warning(f"Mastery recalc failed: {e}", exc_info=True)

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
        grading_mode=grading_mode,
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
    session = db.query(PracticeSession).filter_by(id=session_id, user_id=_user.id).first()
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
    session = db.query(PracticeSession).filter_by(id=session_id, user_id=_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.current_index = body.current_index
    db.commit()
    return {"status": "ok"}


@router.get("/sessions/{session_id}/explanation-stream")
async def explanation_stream(
    session_id: int,
    question_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """SSE — stream AI explanation for a submitted answer."""
    attempt = db.query(QuestionAttempt).filter_by(
        session_id=session_id, question_id=question_id
    ).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Question attempt not found")

    question = _get_question_by_id(db, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    session = db.query(PracticeSession).filter_by(id=session_id).first()
    content = _parse_content_json(question)
    correct_answer = str(content.get("correct_answer", "") or content.get("correct_answers", ""))
    subject_name = session.subject.name if session and session.subject else ""
    user_answer = attempt.user_answer or ""

    async def event_stream():
        try:
            async for chunk in generate_explanation_stream(
                question_text=content.get("question_text", ""),
                user_answer=user_answer,
                correct_answer=correct_answer,
                subject_name=subject_name,
                options=content.get("options"),
                api_key=current_user.api_key,
            ):
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                await asyncio.sleep(0.01)
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _parse_content_json(question: Question) -> dict:
    if isinstance(question.content_json, dict):
        return question.content_json
    return json.loads(question.content_json)


# ── Scoring config ──

SCORING_CONFIG = {
    "single_choice": 3,
    "multiple_choice": 4,
    "fill_blank": 5,
    "short_answer": 10,
    "calculation": 15,
    "proof": 20,
}


@router.get("/scoring-config")
def scoring_config():
    """Return point values per question type."""
    return SCORING_CONFIG


@router.post("/sessions/{session_id}/self-judge")
def self_judge(
    session_id: int,
    question_id: int = Query(...),
    is_correct: bool = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """User self-judges a subjective question."""
    attempt = db.query(QuestionAttempt).filter_by(
        session_id=session_id, question_id=question_id
    ).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    session = db.query(PracticeSession).filter_by(
        id=session_id, user_id=_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Only allow self-judge for subjective (is_correct was None)
    if attempt.is_correct is not None:
        raise HTTPException(status_code=400, detail="Already graded")

    attempt.is_correct = is_correct
    attempt.attempted_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "is_correct": is_correct}


@router.get("/sessions/{session_id}/score")
def session_score(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Calculate total score for a completed session."""
    session = db.query(PracticeSession).filter_by(
        id=session_id, user_id=_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    attempts = db.query(QuestionAttempt).filter_by(session_id=session_id).all()
    questions = {q.id: q for q in db.query(Question).filter(
        Question.id.in_([a.question_id for a in attempts])
    ).all()}

    total = 0
    max_total = 0
    detail = []
    for att in attempts:
        q = questions.get(att.question_id)
        if not q:
            continue
        pts = SCORING_CONFIG.get(q.question_type, 3)
        max_total += pts
        earned = pts if att.is_correct else 0
        total += earned
        detail.append({
            "question_id": q.id,
            "question_type": q.question_type,
            "is_correct": att.is_correct,
            "points": pts,
            "earned": earned,
        })

    return {
        "total_score": total,
        "max_score": max_total,
        "percentage": round(total / max_total * 100, 1) if max_total > 0 else 0,
        "graded_count": sum(1 for a in attempts if a.is_correct is not None),
        "total_count": len(attempts),
        "details": detail,
    }
