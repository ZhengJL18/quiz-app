"""Mastery schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ChapterMasteryOut(BaseModel):
    id: int
    user_id: int
    chapter_id: int
    star_level: int
    mastery_score: float
    accuracy_score: float
    consistency_score: float
    difficulty_score: float
    speed_score: float
    total_attempts: int
    correct_attempts: int
    last_calculated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SubjectMasterySummary(BaseModel):
    subject_id: int
    subject_name: str
    avg_mastery_score: float
    avg_star_level: float
    total_chapters: int
    mastered_chapters: int  # star_level >= 4
    chapter_masteries: list[ChapterMasteryOut]


class DashboardSummary(BaseModel):
    total_subjects: int
    global_avg_score: float
    global_avg_star: float
    total_chapters: int
    total_mastered_chapters: int
    subjects: list[SubjectMasterySummary]
