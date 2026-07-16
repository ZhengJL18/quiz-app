"""Chapter schemas — including recursive tree structure."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class ChapterCreate(BaseModel):
    subject_id: int
    name: str
    description: Optional[str] = None
    order_index: int = 0
    parent_chapter_id: Optional[int] = None
    level: int = 1
    is_leaf: bool = False


class ChapterUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    order_index: Optional[int] = None
    is_leaf: Optional[bool] = None


class ChapterOut(BaseModel):
    id: int
    subject_id: int
    name: str
    description: Optional[str] = None
    order_index: int
    parent_chapter_id: Optional[int] = None
    level: int
    is_leaf: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MasterySummary(BaseModel):
    """Lightweight mastery data attached to leaf nodes in the tree."""
    star_level: int = 0
    mastery_score: float = 0.0
    total_attempts: int = 0
    correct_attempts: int = 0


class ChapterTreeNode(BaseModel):
    """Recursive tree node for the chapter tree API."""
    id: int
    name: str
    level: int
    order_index: int
    is_leaf: bool
    mastery: Optional[MasterySummary] = None
    question_count: int = 0
    children: List["ChapterTreeNode"] = []

    class Config:
        from_attributes = True
