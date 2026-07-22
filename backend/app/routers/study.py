"""Study router — lesson-practice mode.

Key design: POST /lesson-practice returns immediately (<1s) with existing data.
AI generation happens in a background task. The frontend connects to SSE
/lesson-stream to receive streaming content as it's generated.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.ai_service.generators import (
    generate_lesson_content,
    generate_lesson_content_stream,
    generate_questions,
)
from app.db.engine import get_db, SessionLocal
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
logger = logging.getLogger("uvicorn.error")


class LessonContentUpdate(BaseModel):
    content: str

# Track which chapters are currently being generated (avoid duplicate BG tasks)
# Separate sets for lesson vs question generation so they don't block each other
_generating_lesson: set[int] = set()
_generating_questions: set[int] = set()
_bg_semaphore = asyncio.Semaphore(3)  # limit concurrent BG AI tasks


async def _bg_generate_lesson(chapter_id: int, chapter_name: str, subject_name: str, prompt_style: str | None, api_key: str | None = None):
    """Background task: generate lesson content and cache it."""
    db = SessionLocal()
    try:
        full = ""
        async for chunk in generate_lesson_content_stream(
            chapter_name=chapter_name,
            subject_name=subject_name,
            prompt_style=prompt_style,
            api_key=api_key,
        ):
            full += chunk
        if full:
            chapter = db.query(Chapter).filter_by(id=chapter_id).first()
            if chapter:
                from app.services.vault_manager import get_vault
                from app.db.models import Subject
                subj = db.query(Subject).filter_by(id=chapter.subject_id).first()
                if subj:
                    vault = get_vault(subj.user_id)
                    safe_subj = "".join(c for c in subj.name if c.isalnum() or c in " _-（）()").strip()
                    safe_ch = "".join(c for c in chapter.name if c.isalnum() or c in " _-（）()").strip()
                    vault_path = f"讲义/{safe_subj}/{safe_ch}.md"
                    vault.write(vault_path, full)
                    chapter.description = vault_path
                else:
                    chapter.description = full
                db.commit()
                logger.info(f"BG lesson cached for chapter {chapter_id}")
    except Exception as e:
        logger.warning(f"BG lesson gen failed for chapter {chapter_id}: {e}")
    finally:
        db.close()
        _generating_lesson.discard(chapter_id)


async def _bg_generate_questions(chapter_id: int, subject_name: str, chapter_name: str, count: int, prompt_style: str | None, api_key: str | None = None):
    """Background task: generate more questions for a chapter."""
    db = SessionLocal()
    try:
        chapter = db.query(Chapter).filter_by(id=chapter_id).first()
        if not chapter: return
        subject = db.query(Subject).filter_by(id=chapter.subject_id).first()
        if not subject: return
        generated = await generate_questions(api_key=api_key,
            subject_name=subject_name,
            chapter_name=chapter_name,
            count=count,
            difficulty_range=(1, 5),
            prompt_style=prompt_style,
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
        db.commit()
        logger.info(f"BG generated {len(generated)} questions for chapter {chapter_id}")
    except Exception as e:
        logger.warning(f"BG question gen failed for chapter {chapter_id}: {e}")
    finally:
        _generating_questions.discard(chapter_id)
        db.close()


@router.post("/lesson-practice", response_model=LessonPracticeResponse)
async def lesson_practice(
    body: LessonPracticeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a lesson-practice session. Returns IMMEDIATELY — no AI blocking."""
    # 1. Find chapter (must be a leaf)
    chapter = db.query(Chapter).filter_by(id=body.chapter_id, is_leaf=True).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found or not a leaf chapter")

    subject = db.query(Subject).filter_by(id=chapter.subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    # 2. Lesson content — read from vault using DB pointer
    from app.services.vault_manager import get_vault
    vault = get_vault(current_user.id)
    vault_path = chapter.description or ""
    lesson_content = ""
    if vault_path and not vault_path.startswith("<"):
        # New format: vault path like "knowledge/高等数学/lessons/极限.md" or "讲义/高等数学/极限.md"
        lesson_content = vault.read(vault_path) or ""
    else:
        # Legacy: description contains full text, not a path
        lesson_content = vault_path

    # 3. Existing questions
    existing_qs = (
        db.query(Question)
        .filter(Question.chapter_id == chapter.id)
        .order_by(Question.id)
        .all()
    )

    # If no questions at all, generate one seed so the lesson isn't empty
    all_questions = list(existing_qs[:body.question_count])
    used_count = len(all_questions)

    # 4. Create session immediately (fast DB ops only)
    question_ids = [q.id for q in all_questions]
    session = PracticeSession(
        mode="lesson",
        subject_id=subject.id,
        chapter_id=chapter.id,
        user_id=current_user.id,
        questions_order=json.dumps(question_ids, ensure_ascii=False),
        lesson_content=lesson_content or "",
    )
    db.add(session)
    db.flush()

    for qid in question_ids:
        attempt = QuestionAttempt(session_id=session.id, question_id=qid, is_correct=None)
        db.add(attempt)

    db.commit()
    db.refresh(session)

    # 5. Fire-and-forget: background AI generation (don't block response)
    if not lesson_content and chapter.id not in _generating_lesson:
        _generating_lesson.add(chapter.id)
        asyncio.create_task(_bg_generate_lesson(
            chapter.id, chapter.name, subject.name, subject.prompt_style, current_user.api_key
        ))

    if used_count < body.question_count and chapter.id not in _generating_questions:
        _generating_questions.add(chapter.id)
        asyncio.create_task(_bg_generate_questions(
            chapter.id, subject.name, chapter.name,
            body.question_count - used_count, subject.prompt_style, current_user.api_key
        ))

    return LessonPracticeResponse(
        session_id=session.id,
        lesson_content=lesson_content,  # empty if BG task is running
        questions=[QuestionOut.model_validate(q) for q in all_questions],
        total_count=len(all_questions),
    )


@router.post("/pre-generate")
async def pre_generate(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pre-generate lesson content AND questions for ALL leaf chapters that lack them.

    Returns immediately — generation runs in background.
    """
    all_leaf = db.query(Chapter).filter(Chapter.is_leaf == True).all()
    seen = set()
    unique = []
    for ch in all_leaf:
        if ch.id not in seen:
            seen.add(ch.id)
            unique.append(ch)

    started_lesson = 0
    started_questions = 0
    for chapter in unique:
        subject = db.query(Subject).filter_by(id=chapter.subject_id).first()
        subj_name = subject.name if subject else ""
        subj_style = subject.prompt_style if subject else None

        # Generate lesson if missing
        if not chapter.description and chapter.id not in _generating_lesson:
            _generating_lesson.add(chapter.id)
            async def _run_lesson(cid=chapter.id, cname=chapter.name, sname=subj_name, style=subj_style, key=current_user.api_key):
                async with _bg_semaphore:
                    await _bg_generate_lesson(cid, cname, sname, style, key)
            asyncio.create_task(_run_lesson())
            started_lesson += 1

        # Generate questions if chapter has fewer than 3
        q_count = db.query(func.count(Question.id)).filter(Question.chapter_id == chapter.id).scalar()
        if q_count < 3 and chapter.id not in _generating_questions:
            _generating_questions.add(chapter.id)
            async def _run_q(cid=chapter.id, sname=subj_name, cname=chapter.name, style=subj_style, key=current_user.api_key):
                async with _bg_semaphore:
                    await _bg_generate_questions(cid, sname, cname, 8, style, key)
            asyncio.create_task(_run_q())
            started_questions += 1

    return {
        "message": f"Started: {started_lesson} lessons + {started_questions} question sets",
        "total_leaf_chapters": len(unique),
    }


def _resolve_chapter_path(db: Session, chapter_id: int) -> tuple[str, list[str]]:
    """Resolve full chapter hierarchy with order-index prefixes: (subject, [01_章, 01_课时])."""
    from app.db.models import Chapter, Subject
    ch = db.query(Chapter).filter_by(id=chapter_id).first()
    if not ch:
        return ("", [])
    subj = db.query(Subject).filter_by(id=ch.subject_id).first()
    subject_name = subj.name if subj else ""
    parts = [(ch.order_index, ch.name)]
    current = ch
    while current.parent_chapter_id:
        parent = db.query(Chapter).filter_by(id=current.parent_chapter_id).first()
        if not parent:
            break
        parts.insert(0, (parent.order_index, parent.name))
        current = parent
    formatted = []
    for i, (order_idx, name) in enumerate(parts):
        if i < len(parts) - 1:
            formatted.append(f"{order_idx:02d}_{name}")
        else:
            formatted.append(name)
    return (subject_name, formatted)


@router.get("/lesson-stream")
async def lesson_stream(
    chapter_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """SSE endpoint — real-time streaming from DeepSeek API for lesson content."""
    chapter = db.query(Chapter).filter_by(id=chapter_id, is_leaf=True).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    subject = db.query(Subject).filter_by(id=chapter.subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    # If cached, stream chunks instantly (visual streaming effect)
    if chapter.description:
        async def cached_stream():
            content = chapter.description
            chunk_size = 80
            for i in range(0, len(content), chunk_size):
                chunk = content[i:i + chunk_size]
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                await asyncio.sleep(0.01)
            yield f"data: {json.dumps({'done': True, 'cached': True, 'content': content})}\n\n"
        return StreamingResponse(cached_stream(), media_type="text/event-stream")

    # Not cached — stream directly from DeepSeek API in real-time, then cache result
    async def live_stream():
        full = ""
        try:
            async for chunk in generate_lesson_content_stream(
                chapter_name=chapter.name,
                subject_name=subject.name,
                prompt_style=subject.prompt_style,
                api_key=current_user.api_key or None,
            ):
                full += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                await asyncio.sleep(0.01)  # Small yield to keep SSE flowing

            # Cache to vault + DB pointer
            if full:
                try:
                    bg_db = SessionLocal()
                    ch = bg_db.query(Chapter).filter_by(id=chapter_id).first()
                    if ch:
                        from app.services.vault_manager import get_vault
                        subj_name, path_parts = _resolve_chapter_path(bg_db, chapter_id)
                        if subj_name and path_parts:
                            subj = bg_db.query(Subject).filter_by(id=ch.subject_id).first()
                            if subj:
                                vault = get_vault(subj.user_id)
                                vault_path = vault.lesson_path(subj_name, path_parts)
                                vault.write(vault_path, full)
                                ch.description = vault_path
                        else:
                            ch.description = full
                        bg_db.commit()
                    bg_db.close()
                except Exception as e:
                    logger.warning(f"Failed to cache lesson for ch{chapter_id}: {e}")

            yield f"data: {json.dumps({'done': True, 'content': full})}\n\n"
        except Exception as e:
            logger.warning(f"Lesson stream failed for ch{chapter_id}: {e}")
            yield f"data: {json.dumps({'error': f'生成失败：{str(e)[:200]}'})}\n\n"

    return StreamingResponse(live_stream(), media_type="text/event-stream")


@router.put("/chapter-lesson/{chapter_id}")
def update_chapter_lesson(
    chapter_id: int,
    body: LessonContentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save user-edited lesson content. Writes to vault, stores pointer in DB."""
    chapter = db.query(Chapter).filter_by(id=chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    # Determine vault path
    from app.services.vault_manager import get_vault
    from app.db.models import Subject
    subject = db.query(Subject).filter_by(id=chapter.subject_id).first()
    if subject:
        vault = get_vault(current_user.id)
        safe_subj = "".join(c for c in subject.name if c.isalnum() or c in " _-（）()").strip()
        safe_ch = "".join(c for c in chapter.name if c.isalnum() or c in " _-（）()").strip()
        vault_path = f"讲义/{safe_subj}/{safe_ch}.md"
        vault.write(vault_path, body.content)
        chapter.description = vault_path  # Store pointer
    else:
        chapter.description = body.content  # Fallback
    db.commit()
    return {"ok": True}


@router.delete("/chapter-lesson/{chapter_id}")
def delete_chapter_lesson(
    chapter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clear cached lesson content for a chapter (allows regeneration)."""
    chapter = db.query(Chapter).filter_by(id=chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    chapter.description = None
    db.commit()
    return {"ok": True}
