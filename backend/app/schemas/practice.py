"""Practice session schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.schemas.question import QuestionOut


# ── Lesson Practice ──

class LessonPracticeRequest(BaseModel):
    chapter_id: int
    question_count: int = 8


class LessonPracticeResponse(BaseModel):
    session_id: int
    lesson_content: str
    questions: list[QuestionOut]
    total_count: int


# ── Pure Practice ──

class PurePracticeRequest(BaseModel):
    subject_id: int
    chapter_id: Optional[int] = None
    count: int = 1


class PurePracticeResponse(BaseModel):
    session_id: int
    questions: list[QuestionOut]


# ── Answer Submission ──

class SubmitAnswerRequest(BaseModel):
    question_id: int
    user_answer: str
    time_spent_seconds: int


class SubmitAnswerResponse(BaseModel):
    is_correct: Optional[bool] = None
    explanation: str
    next_question: Optional[QuestionOut] = None


# ── Session state ──

class SessionOut(BaseModel):
    id: int
    mode: str
    subject_id: int
    chapter_id: Optional[int] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    is_completed: bool
    current_index: int
    questions_order: str
    lesson_content: Optional[str] = None
    questions: list[QuestionOut] = []

    class Config:
        from_attributes = True


class UpdateCurrentIndexRequest(BaseModel):
    current_index: int
