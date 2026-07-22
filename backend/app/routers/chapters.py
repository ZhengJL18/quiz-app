"""Chapters router — SQLite for web API, vault synced on writes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.db.engine import get_db
from app.db.models import User, Subject, Chapter, ChapterMastery, Question
from app.dependencies import get_current_user
from app.schemas.chapter import (
    ChapterCreate, ChapterUpdate, ChapterOut,
    ChapterTreeNode, MasterySummary,
)
from app.vault import manager as vault

router = APIRouter()


# ── Tree builder (from SQLite) ──

def _build_tree(chapters: list[Chapter], user_id: int) -> list[ChapterTreeNode]:
    """Build recursive chapter tree from SQLite models."""
    leaf_ids = [c.id for c in chapters if c.is_leaf]
    mastery_map = {}
    if leaf_ids:
        records = (
            __import__('sqlalchemy.orm', fromlist=['Session']).Session.object_session(chapters[0])
            .query(ChapterMastery)
            .filter(ChapterMastery.user_id == user_id, ChapterMastery.chapter_id.in_(leaf_ids))
            .all()
        )
        mastery_map = {r.chapter_id: r for r in records}

    node_map = {}
    for c in chapters:
        mastery = mastery_map.get(c.id)
        qcount = len(c.questions) if hasattr(c, 'questions') and c.questions else 0
        node_map[c.id] = ChapterTreeNode(
            id=c.id, name=c.name, level=c.level,
            order_index=c.order_index, parent_chapter_id=c.parent_chapter_id,
            is_leaf=c.is_leaf,
            mastery=MasterySummary(star_level=mastery.star_level, mastery_score=mastery.mastery_score,
                                   total_attempts=mastery.total_attempts, correct_attempts=mastery.correct_attempts) if mastery else None,
            question_count=qcount,
        )

    roots = []
    for c in chapters:
        node = node_map[c.id]
        if c.parent_chapter_id and c.parent_chapter_id in node_map:
            node_map[c.parent_chapter_id].children.append(node)
        else:
            roots.append(node)

    for node in node_map.values():
        node.children.sort(key=lambda x: x.order_index)
    roots.sort(key=lambda x: x.order_index)
    return roots


@router.get("/subjects/{subject_id}/chapters", response_model=list[ChapterTreeNode])
def get_chapter_tree(subject_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    subject = db.query(Subject).filter_by(id=subject_id, user_id=current_user.id, is_active=True).first()
    if not subject: raise HTTPException(status_code=404, detail="Subject not found")
    chapters = db.query(Chapter).options(joinedload(Chapter.questions)).filter(Chapter.subject_id == subject_id).order_by(Chapter.order_index).all()
    if not chapters: return []
    return _build_tree(chapters, current_user.id)


@router.post("/chapters", response_model=ChapterOut, status_code=201)
def create_chapter(body: ChapterCreate, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    chapter = Chapter(**body.model_dump())
    db.add(chapter); db.commit(); db.refresh(chapter)
    # Sync to vault
    subject = db.query(Subject).filter_by(id=body.subject_id).first()
    if subject:
        vault.ensure_chapter(subject.name, body.name, body.level, "", body.is_leaf)
    return chapter


@router.put("/chapters/{chapter_id}", response_model=ChapterOut)
def update_chapter(chapter_id: int, body: ChapterUpdate, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    chapter = db.query(Chapter).filter_by(id=chapter_id).first()
    if not chapter: raise HTTPException(status_code=404)
    old_name = chapter.name
    for key, val in body.model_dump(exclude_unset=True).items():
        setattr(chapter, key, val)
    db.commit(); db.refresh(chapter)
    # Sync rename to vault
    if body.name and body.name != old_name and chapter.subject:
        vault.rename_subject(chapter.subject.name, body.name)
    return chapter


@router.delete("/chapters/{chapter_id}", status_code=204)
def delete_chapter(chapter_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    chapter = db.query(Chapter).filter_by(id=chapter_id).first()
    if not chapter: raise HTTPException(status_code=404)
    # Cascade delete descendants + questions
    all_ids = {chapter_id}
    queue = [chapter_id]
    while queue:
        pid = queue.pop(0)
        for (cid,) in db.query(Chapter.id).filter(Chapter.parent_chapter_id == pid).all():
            if cid not in all_ids:
                all_ids.add(cid); queue.append(cid)
    for cid in all_ids:
        db.query(Question).filter(Question.chapter_id == cid).delete()
    for cid in sorted(all_ids, reverse=True):
        db.query(Chapter).filter(Chapter.id == cid).delete()
    db.commit()
    # Sync to vault
    subj = db.query(Subject).filter_by(id=chapter.subject_id).first()
    if subj:
        vault.delete_chapter(subj.name, chapter.name)
    return None
