"""Vocab card schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class VocabCardOut(BaseModel):
    id: int
    word: str
    definition: str
    example_sentence: Optional[str] = None
    pronunciation: Optional[str] = None
    root_analysis: Optional[str] = None
    synonyms: Optional[str] = None
    antonyms: Optional[str] = None
    collocations: Optional[str] = None
    difficulty: int
    subject_id: Optional[int] = None
    created_by: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class VocabGenerateRequest(BaseModel):
    subject_name: str = "英语四六级"
    count: int = 10
    difficulty: int = 1


class VocabReviewItem(BaseModel):
    review_id: int
    vocab_card_id: int
    word: str
    definition: str
    example_sentence: Optional[str] = None
    pronunciation: Optional[str] = None
    root_analysis: Optional[str] = None
    synonyms: Optional[str] = None
    antonyms: Optional[str] = None
    collocations: Optional[str] = None
    next_review_at: Optional[datetime] = None
    interval_days: float
    ease_factor: float
    review_count: int

    model_config = {"from_attributes": True}


class VocabReviewRequest(BaseModel):
    vocab_card_id: int
    quality: int  # 0-5 (0=forgot, 3=fuzzy, 5=knew)
