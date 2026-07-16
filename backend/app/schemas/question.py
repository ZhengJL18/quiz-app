"""Question schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class QuestionOut(BaseModel):
    id: int
    subject_id: int
    chapter_id: int
    question_type: str
    content_json: str
    difficulty: int
    has_latex: bool
    created_by: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
