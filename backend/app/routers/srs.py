"""SRS router — spaced repetition scheduling."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.engine import get_db
from app.db.models import (
    Question,
    SRSSchedule,
    User,
    WrongBook,
)
from app.dependencies import get_current_user
from app.schemas.question import QuestionOut
from app.schemas.srs import SRSReviewItem, SRSReviewRequest
from app.services.srs_algorithm import sm2_calculate

router = APIRouter()


@router.get("/review-today", response_model=list[SRSReviewItem])
def get_review_today(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all SRS entries due for review."""
    now = datetime.now(timezone.utc)
    srs_entries = (
        db.query(SRSSchedule)
        .join(WrongBook, SRSSchedule.wrong_book_id == WrongBook.id)
        .filter(SRSSchedule.next_review_at <= now, WrongBook.user_id == current_user.id)
        .order_by(SRSSchedule.next_review_at.asc())
        .all()
    )

    results: list[SRSReviewItem] = []
    for srs in srs_entries:
        wrong_entry = db.query(WrongBook).filter_by(id=srs.wrong_book_id).first()
        if not wrong_entry:
            continue

        question = db.query(Question).filter_by(id=wrong_entry.question_id).first()
        if not question:
            continue

        results.append(
            SRSReviewItem(
                srs_id=srs.id,
                wrong_book_id=srs.wrong_book_id,
                question_id=wrong_entry.question_id,
                question=QuestionOut.model_validate(question) if question else None,
                ai_explanation=wrong_entry.ai_explanation,
                user_note=wrong_entry.user_note,
                mastery_status=wrong_entry.mastery_status,
                next_review_at=srs.next_review_at,
                interval_days=srs.interval_days,
                ease_factor=srs.ease_factor,
                review_count=srs.review_count,
            )
        )

    return results


@router.post("/review")
def submit_review(
    body: SRSReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a review quality rating and update the SRS schedule."""
    if body.quality < 0 or body.quality > 5:
        raise HTTPException(status_code=400, detail="Quality must be between 0 and 5")

    wrong_entry = db.query(WrongBook).filter_by(id=body.wrong_book_id, user_id=current_user.id).first()
    if not wrong_entry:
        raise HTTPException(status_code=404, detail="Wrong book entry not found")

    srs = (
        db.query(SRSSchedule)
        .filter_by(wrong_book_id=body.wrong_book_id)
        .first()
    )
    if not srs:
        raise HTTPException(status_code=404, detail="SRS schedule not found for this entry")

    # Calculate new SM-2 params
    result = sm2_calculate(
        quality=body.quality,
        interval_days=srs.interval_days,
        ease_factor=srs.ease_factor,
        review_count=srs.review_count,
    )

    # Update SRS
    now = datetime.now(timezone.utc)
    from datetime import timedelta
    srs.interval_days = result["interval_days"]
    srs.ease_factor = result["ease_factor"]
    srs.review_count = result["review_count"]
    srs.last_review_at = now
    srs.next_review_at = now + timedelta(days=result["interval_days"])

    if body.quality >= 4:
        srs.last_performance = "remembered"
    elif body.quality >= 2:
        srs.last_performance = "partial"
    else:
        srs.last_performance = "forgot"

    # Update mastery_status on wrong book
    if body.quality >= 4 and result["interval_days"] >= 21:
        wrong_entry.mastery_status = "mastered"
    elif body.quality >= 4:
        wrong_entry.mastery_status = "reviewing"
    else:
        wrong_entry.mastery_status = "not_mastered"

    db.commit()

    return {
        "status": "ok",
        "next_review_at": srs.next_review_at.isoformat(),
        "interval_days": srs.interval_days,
        "ease_factor": srs.ease_factor,
        "review_count": srs.review_count,
    }
