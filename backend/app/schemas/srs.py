"""SRS schedule schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.schemas.question import QuestionOut


class SRSScheduleOut(BaseModel):
    id: int
    wrong_book_id: int
    next_review_at: Optional[datetime] = None
    interval_days: float
    ease_factor: float
    review_count: int
    last_review_at: Optional[datetime] = None
    last_performance: Optional[str] = None

    class Config:
        from_attributes = True


class SRSReviewItem(BaseModel):
    """A review item combining SRS + wrong book + question data."""
    srs_id: int
    wrong_book_id: int
    question_id: int
    question: Optional[QuestionOut] = None
    ai_explanation: Optional[str] = None
    user_note: Optional[str] = None
    mastery_status: str
    next_review_at: Optional[datetime] = None
    interval_days: float
    ease_factor: float
    review_count: int

    class Config:
        from_attributes = True


class SRSReviewRequest(BaseModel):
    wrong_book_id: int
    quality: int  # 0-5
