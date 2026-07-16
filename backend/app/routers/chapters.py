"""Chapters router — tree structure with mastery data."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.db.engine import get_db
from app.db.models import User, Subject, Chapter, ChapterMastery
from app.dependencies import get_current_user
from app.schemas.chapter import (
    ChapterCreate, ChapterUpdate, ChapterOut,
    ChapterTreeNode, MasterySummary,
)

router = APIRouter()


def _build_tree(chapters: list[Chapter], user_id: int) -> list[ChapterTreeNode]:
    """Build a recursive tree from a flat list of chapters."""
    # Index mastery data by chapter_id
    mastery_map = {}
    if chapters:
        chapter_ids = [c.id for c in chapters]
        records = (
            Session.object_session(chapters[0])
            .query(ChapterMastery)
            .filter(ChapterMastery.user_id == user_id, ChapterMastery.chapter_id.in_(chapter_ids))
            .all()
        )
        mastery_map = {m.chapter_id: m for m in records}

    # Count questions per chapter (only leaf nodes have questions)
    question_counts = {}
    if chapters:
        from sqlalchemy import func
        from app.db.models import Question
        chapter_ids = [c.id for c in chapters if c.is_leaf]
        if chapter_ids:
            rows = (
                Session.object_session(chapters[0])
                .query(Question.chapter_id, func.count(Question.id))
                .filter(Question.chapter_id.in_(chapter_ids))
                .group_by(Question.chapter_id)
                .all()
            )
            question_counts = {row[0]: row[1] for row in rows}

    # Build lookup by id
    node_map = {}
    for c in chapters:
        mastery = mastery_map.get(c.id)
        qcount = question_counts.get(c.id, 0)
        node_map[c.id] = ChapterTreeNode(
            id=c.id,
            name=c.name,
            level=c.level,
            order_index=c.order_index,
            is_leaf=c.is_leaf,
            mastery=MasterySummary(
                star_level=mastery.star_level,
                mastery_score=mastery.mastery_score,
                total_attempts=mastery.total_attempts,
                correct_attempts=mastery.correct_attempts,
            ) if mastery and c.is_leaf else None,
            question_count=qcount,
            children=[],
        )

    # Build tree
    roots = []
    for c in chapters:
        node = node_map[c.id]
        if c.parent_chapter_id and c.parent_chapter_id in node_map:
            node_map[c.parent_chapter_id].children.append(node)
        else:
            roots.append(node)

    # Sort children
    for node in node_map.values():
        node.children.sort(key=lambda x: x.order_index)

    roots.sort(key=lambda x: x.order_index)
    return roots


@router.get("/subjects/{subject_id}/chapters", response_model=list[ChapterTreeNode])
def get_chapter_tree(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the full chapter tree for a subject, with mastery data on leaf nodes."""
    subject = db.query(Subject).filter_by(id=subject_id, is_active=True).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    chapters = (
        db.query(Chapter)
        .filter(Chapter.subject_id == subject_id)
        .order_by(Chapter.order_index)
        .all()
    )

    if not chapters:
        # Return empty list rather than 404 — subject may have no chapters yet
        return []

    return _build_tree(chapters, current_user.id)


@router.get("/chapters/{chapter_id}", response_model=ChapterOut)
def get_chapter(
    chapter_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    chapter = db.query(Chapter).filter_by(id=chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return chapter


@router.post("/chapters", response_model=ChapterOut, status_code=201)
def create_chapter(
    body: ChapterCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    chapter = Chapter(**body.model_dump())
    db.add(chapter)
    db.commit()
    db.refresh(chapter)
    return chapter


@router.put("/chapters/{chapter_id}", response_model=ChapterOut)
def update_chapter(
    chapter_id: int,
    body: ChapterUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    chapter = db.query(Chapter).filter_by(id=chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    for key, val in body.model_dump(exclude_unset=True).items():
        setattr(chapter, key, val)
    db.commit()
    db.refresh(chapter)
    return chapter
