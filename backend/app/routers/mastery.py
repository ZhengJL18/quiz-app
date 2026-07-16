"""Mastery router — query chapter and subject mastery data."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.engine import get_db
from app.db.models import (
    Chapter,
    ChapterMastery,
    Subject,
    User,
)
from app.dependencies import get_current_user
from app.schemas.mastery import (
    ChapterMasteryOut,
    DashboardSummary,
    SubjectMasterySummary,
)

router = APIRouter()


@router.get("/chapter/{chapter_id}", response_model=ChapterMasteryOut)
def get_chapter_mastery(
    chapter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return detailed ChapterMastery for the current user and chapter."""
    mastery = (
        db.query(ChapterMastery)
        .filter_by(user_id=current_user.id, chapter_id=chapter_id)
        .first()
    )
    if not mastery:
        raise HTTPException(status_code=404, detail="No mastery data found for this chapter")
    return mastery


@router.get("/subject/{subject_id}", response_model=list[ChapterMasteryOut])
def get_subject_mastery(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return ChapterMastery for all leaf chapters in a subject."""
    leaf_ids = (
        db.query(Chapter.id)
        .filter(Chapter.subject_id == subject_id, Chapter.is_leaf.is_(True))
        .subquery()
    )
    records = (
        db.query(ChapterMastery)
        .filter(
            ChapterMastery.user_id == current_user.id,
            ChapterMastery.chapter_id.in_(leaf_ids),
        )
        .all()
    )
    return records


@router.get("/dashboard", response_model=DashboardSummary)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a dashboard summary of all subjects, scores, and star distributions."""
    subjects = db.query(Subject).filter_by(is_active=True).order_by(Subject.order_index).all()
    total_chapters = 0
    total_mastered = 0
    all_scores: list[float] = []
    all_stars: list[int] = []
    subject_summaries: list[SubjectMasterySummary] = []

    for subject in subjects:
        leaf_ids = [
            c.id for c in subject.chapters if c.is_leaf
        ]
        if not leaf_ids:
            continue

        masteries = (
            db.query(ChapterMastery)
            .filter(
                ChapterMastery.user_id == current_user.id,
                ChapterMastery.chapter_id.in_(leaf_ids),
            )
            .all()
        )

        if not masteries:
            continue

        scores = [m.mastery_score for m in masteries]
        stars = [m.star_level for m in masteries]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        avg_star = sum(stars) / len(stars) if stars else 0.0
        mastered_count = sum(1 for s in stars if s >= 4)

        total_chapters += len(masteries)
        total_mastered += mastered_count
        all_scores.extend(scores)
        all_stars.extend(stars)

        subject_summaries.append(
            SubjectMasterySummary(
                subject_id=subject.id,
                subject_name=subject.name,
                avg_mastery_score=round(avg_score, 2),
                avg_star_level=round(avg_star, 2),
                total_chapters=len(masteries),
                mastered_chapters=mastered_count,
                chapter_masteries=[ChapterMasteryOut.model_validate(m) for m in masteries],
            )
        )

    global_avg_score = sum(all_scores) / len(all_scores) if all_scores else 0.0
    global_avg_star = sum(all_stars) / len(all_stars) if all_stars else 0.0

    return DashboardSummary(
        total_subjects=len(subject_summaries),
        global_avg_score=round(global_avg_score, 2),
        global_avg_star=round(global_avg_star, 2),
        total_chapters=total_chapters,
        total_mastered_chapters=total_mastered,
        subjects=subject_summaries,
    )
