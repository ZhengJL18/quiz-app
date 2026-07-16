"""Wrong-book schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.schemas.question import QuestionOut


class WrongBookOut(BaseModel):
    id: int
    question_id: int
    first_wrong_at: Optional[datetime] = None
    last_wrong_at: Optional[datetime] = None
    wrong_count: int
    ai_explanation: Optional[str] = None
    user_note: Optional[str] = None
    mastery_status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WrongBookDetail(WrongBookOut):
    question: Optional[QuestionOut] = None


class WrongBookUpdate(BaseModel):
    ai_explanation: Optional[str] = None
    user_note: Optional[str] = None
    mastery_status: Optional[str] = None
