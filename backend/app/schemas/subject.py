"""Subject schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SubjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    prompt_style: Optional[str] = None
    order_index: int = 0


class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    prompt_style: Optional[str] = None
    order_index: Optional[int] = None


class SubjectOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_active: bool
    prompt_style: Optional[str] = None
    order_index: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
