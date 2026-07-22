"""Statistics router — daily & trend analytics."""
from datetime import datetime, timedelta, timezone, date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.engine import get_db
from app.db.models import (
    User, PracticeSession, QuestionAttempt,
    WrongBook, SRSSchedule, VocabReview, ChapterMastery, Chapter, Subject
)
from app.dependencies import get_current_user

router = APIRouter()


@router.get("/daily")
def daily_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Today's learning stats."""
    today = date.today()
    today_start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)

    # Questions completed today
    attempts = (
        db.query(QuestionAttempt)
        .join(PracticeSession)
        .filter(
            PracticeSession.user_id == current_user.id,
            QuestionAttempt.attempted_at >= today_start,
            QuestionAttempt.is_correct != None,
        )
    )
    total_attempts = attempts.count()
    correct_count = attempts.filter(QuestionAttempt.is_correct == True).count()
    total_seconds = db.query(func.coalesce(func.sum(QuestionAttempt.time_spent_seconds), 0)).join(
        PracticeSession
    ).filter(
        PracticeSession.user_id == current_user.id,
        QuestionAttempt.attempted_at >= today_start,
    ).scalar() or 0

    # Reviews completed today
    srs_reviews = db.query(SRSSchedule).join(WrongBook).filter(
        WrongBook.user_id == current_user.id,
        SRSSchedule.last_review_at >= today_start,
    ).count()

    vocab_reviews = db.query(VocabReview).filter(
        VocabReview.last_review_at >= today_start,
    ).count()

    # Session count
    sessions_today = db.query(PracticeSession).filter(
        PracticeSession.user_id == current_user.id,
        PracticeSession.started_at >= today_start,
    ).count()

    # Streak (consecutive days with activity)
    streak = _calculate_streak(db, current_user.id)

    return {
        "date": today.isoformat(),
        "total_attempts": total_attempts,
        "correct_count": correct_count,
        "accuracy_rate": round(correct_count / total_attempts * 100, 1) if total_attempts > 0 else 0,
        "total_seconds": total_seconds,
        "sessions": sessions_today,
        "srs_reviews": srs_reviews,
        "vocab_reviews": vocab_reviews,
        "streak_days": streak,
    }


@router.get("/trends")
def trends(
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Daily trend data for the last N days."""
    start = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (
        db.query(
            func.date(QuestionAttempt.attempted_at).label("day"),
            func.count(QuestionAttempt.id).label("total"),
            func.sum(func.cast(QuestionAttempt.is_correct, type_=__import__('sqlalchemy', fromlist=['Integer']).Integer)).label("correct"),
            func.coalesce(func.sum(QuestionAttempt.time_spent_seconds), 0).label("seconds"),
        )
        .join(PracticeSession)
        .filter(
            PracticeSession.user_id == current_user.id,
            QuestionAttempt.attempted_at >= start,
            QuestionAttempt.attempted_at != None,
        )
        .group_by(func.date(QuestionAttempt.attempted_at))
        .order_by("day")
        .all()
    )

    data = []
    for row in rows:
        data.append({
            "date": str(row.day),
            "total": row.total,
            "correct": row.correct or 0,
            "accuracy": round((row.correct or 0) / row.total * 100, 1) if row.total else 0,
            "seconds": row.seconds or 0,
        })

    return {"days": days, "data": data}


@router.get("/subjects")
def subject_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Per-subject practice distribution."""
    subjects = db.query(Subject).filter(
        Subject.user_id == current_user.id, Subject.is_active == True
    ).all()

    result = []
    for s in subjects:
        attempts = db.query(func.count(QuestionAttempt.id)).join(
            PracticeSession
        ).filter(
            PracticeSession.user_id == current_user.id,
            PracticeSession.subject_id == s.id,
        ).scalar() or 0

        correct = db.query(func.count(QuestionAttempt.id)).join(
            PracticeSession
        ).filter(
            PracticeSession.user_id == current_user.id,
            PracticeSession.subject_id == s.id,
            QuestionAttempt.is_correct == True,
        ).scalar() or 0

        mastery = db.query(func.avg(ChapterMastery.mastery_score)).join(
            Chapter
        ).filter(
            ChapterMastery.user_id == current_user.id,
            Chapter.subject_id == s.id,
        ).scalar()

        result.append({
            "subject_id": s.id,
            "subject_name": s.name,
            "attempts": attempts,
            "correct": correct,
            "accuracy": round(correct / attempts * 100, 1) if attempts > 0 else 0,
            "avg_mastery": round((mastery or 0) * 100, 1),
        })

    return result


def _calculate_streak(db: Session, user_id: int) -> int:
    """Calculate consecutive days with activity."""
    rows = (
        db.query(func.date(QuestionAttempt.attempted_at).label("day"))
        .join(PracticeSession)
        .filter(
            PracticeSession.user_id == user_id,
            QuestionAttempt.attempted_at != None,
        )
        .group_by(func.date(QuestionAttempt.attempted_at))
        .order_by(func.date(QuestionAttempt.attempted_at).desc())
        .all()
    )
    if not rows:
        return 0

    streak = 0
    today = date.today()
    check = today

    for row in rows:
        row_date = row.day
        if isinstance(row_date, str):
            row_date = date.fromisoformat(row_date)
        if row_date == check:
            streak += 1
            check -= timedelta(days=1)
        elif row_date < check:
            break

    return streak
