"""Mastery calculation engine.

Computes per-chapter mastery from historical question attempts.
Also aggregates child-chapter scores up to parent chapters.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import (
    Chapter,
    ChapterMastery,
    PracticeSession,
    Question,
    QuestionAttempt,
)

# Baseline expected time (seconds) per difficulty level 1-5
DIFFICULTY_BASELINE_SECONDS = {1: 30, 2: 60, 3: 120, 4: 180, 5: 300}


def recalculate_chapter_mastery(
    db: Session,
    user_id: int,
    chapter_id: int,
) -> ChapterMastery:
    """Recalculate mastery for *chapter_id* and propagate to parent chapters.

    Steps:
        1. Pull all QuestionAttempt rows for the given user+chapter.
        2. Compute four sub-scores.
        3. Merge into a weighted mastery_score.
        4. Derive star_level with cold-start / difficulty caps.
        5. Upsert the ChapterMastery record.
        6. Recurse up to level-1 and level-2 parents by aggregating children.
    """
    # Gather all attempts for questions in this chapter
    attempts = (
        db.query(QuestionAttempt)
        .join(
            PracticeSession,
            QuestionAttempt.session_id == PracticeSession.id,
        )
        .join(Question, QuestionAttempt.question_id == Question.id)
        .filter(
            PracticeSession.chapter_id == chapter_id,
            QuestionAttempt.attempted_at.isnot(None),
        )
        .all()
    )

    total = len(attempts)
    correct_count = sum(1 for a in attempts if a.is_correct is True)

    if total == 0:
        return _upsert_mastery(db, user_id, chapter_id, ChapterMastery(
            user_id=user_id,
            chapter_id=chapter_id,
            star_level=0,
            mastery_score=0.0,
            accuracy_score=0.0,
            consistency_score=0.0,
            difficulty_score=0.0,
            speed_score=0.0,
            total_attempts=0,
            correct_attempts=0,
        ))

    # ---- 1. accuracy_score (40%) — Bayesian smoothed ----
    accuracy_score = ((correct_count + 1) / (total + 2)) * 100.0

    # ---- 2. consistency_score (25%) — recent 30% vs older 70% ----
    attempts_sorted = sorted(attempts, key=lambda a: a.attempted_at or datetime(1970, 1, 1, tzinfo=timezone.utc))
    if total < 10:
        consistency_score = 100.0
    else:
        split_idx = int(total * 0.7)
        early = attempts_sorted[:split_idx]
        recent = attempts_sorted[split_idx:]
        early_acc = sum(1 for a in early if a.is_correct is True) / len(early) if early else 0.0
        recent_acc = sum(1 for a in recent if a.is_correct is True) / len(recent) if recent else 0.0
        diff = abs(recent_acc - early_acc) * 100.0
        consistency_score = max(100.0 - min(diff * 2, 100.0), 0.0)

    # ---- 3. difficulty_score (20%) — weighted by level ----
    diff_counts: dict[int, int] = {}
    diff_correct: dict[int, int] = {}
    for a in attempts:
        d = a.question.difficulty
        diff_counts[d] = diff_counts.get(d, 0) + 1
        if a.is_correct is True:
            diff_correct[d] = diff_correct.get(d, 0) + 1

    weighted_sum = 0.0
    for d in range(1, 6):
        cnt = diff_counts.get(d, 0)
        if cnt > 0:
            level_acc = (diff_correct.get(d, 0) / cnt) * 100.0
            weighted_sum += level_acc * cnt
    difficulty_score = weighted_sum / total if total > 0 else 0.0

    # ---- 4. speed_score (15%) — compare average time to baseline ----
    total_time = sum(a.time_spent_seconds or 0 for a in attempts)
    avg_time = total_time / total if total > 0 else 0.0
    # Weighted baseline based on the difficulty distribution of attempts
    baseline_sum = 0.0
    for d in range(1, 6):
        cnt = diff_counts.get(d, 0)
        baseline_sum += DIFFICULTY_BASELINE_SECONDS[d] * cnt
    avg_baseline = baseline_sum / total if total > 0 else 1.0
    speed_ratio = min(avg_baseline / avg_time, 1.0) if avg_time > 0 else 1.0
    speed_score = speed_ratio * 100.0

    # ---- Mastery score ----
    mastery_score = (
        accuracy_score * 0.40
        + consistency_score * 0.25
        + difficulty_score * 0.20
        + speed_score * 0.15
    )

    # ---- Star level ----
    if total < 3:
        star_level = 0  # cold start
    else:
        if mastery_score >= 80:
            star_level = 5
        elif mastery_score >= 60:
            star_level = 4
        elif mastery_score >= 40:
            star_level = 3
        elif mastery_score >= 20:
            star_level = 2
        elif mastery_score > 0:
            star_level = 1
        else:
            star_level = 0

    # Cap: never attempted a difficulty >= 3 question → max 4 stars
    max_difficulty = max((a.question.difficulty for a in attempts), default=0)
    if max_difficulty < 3 and star_level == 5:
        star_level = 4

    # Upsert leaf chapter
    mastery = _upsert_mastery(
        db,
        user_id,
        chapter_id,
        ChapterMastery(
            user_id=user_id,
            chapter_id=chapter_id,
            star_level=star_level,
            mastery_score=round(mastery_score, 2),
            accuracy_score=round(accuracy_score, 2),
            consistency_score=round(consistency_score, 2),
            difficulty_score=round(difficulty_score, 2),
            speed_score=round(speed_score, 2),
            total_attempts=total,
            correct_attempts=correct_count,
            last_calculated_at=datetime.now(timezone.utc),
        ),
    )

    # ---- Propagate to parent chapters ----
    _recalculate_parent_mastery(db, user_id, chapter_id)

    return mastery


def _upsert_mastery(
    db: Session,
    user_id: int,
    chapter_id: int,
    defaults_obj: ChapterMastery,
) -> ChapterMastery:
    """Create or update a ChapterMastery row, returning the row."""
    existing = (
        db.query(ChapterMastery)
        .filter_by(user_id=user_id, chapter_id=chapter_id)
        .first()
    )
    if existing:
        existing.star_level = defaults_obj.star_level
        existing.mastery_score = defaults_obj.mastery_score
        existing.accuracy_score = defaults_obj.accuracy_score
        existing.consistency_score = defaults_obj.consistency_score
        existing.difficulty_score = defaults_obj.difficulty_score
        existing.speed_score = defaults_obj.speed_score
        existing.total_attempts = defaults_obj.total_attempts
        existing.correct_attempts = defaults_obj.correct_attempts
        existing.last_calculated_at = defaults_obj.last_calculated_at
        db.flush()
        return existing
    else:
        db.add(defaults_obj)
        db.flush()
        return defaults_obj


def _recalculate_parent_mastery(db: Session, user_id: int, chapter_id: int) -> None:
    """Aggregate child mastery into level-1 and level-2 parent chapters."""
    chapter = db.query(Chapter).filter_by(id=chapter_id).first()
    if not chapter:
        return

    seen: set[int] = set()

    # Walk up from the current chapter to its parent chain
    parent = chapter
    while parent.parent_chapter_id is not None:
        parent = db.query(Chapter).filter_by(id=parent.parent_chapter_id).first()
        if not parent or parent.id in seen:
            break
        seen.add(parent.id)

        children = db.query(Chapter).filter_by(parent_chapter_id=parent.id).all()
        if not children:
            continue

        child_ids = [c.id for c in children]
        child_masteries = (
            db.query(ChapterMastery)
            .filter(
                ChapterMastery.user_id == user_id,
                ChapterMastery.chapter_id.in_(child_ids),
            )
            .all()
        )

        if not child_masteries:
            continue

        total_attempts = sum(m.total_attempts for m in child_masteries)
        correct_attempts = sum(m.correct_attempts for m in child_masteries)
        if total_attempts == 0:
            continue

        # Weighted average by total_attempts
        weight_sum = sum(m.total_attempts for m in child_masteries)
        agg = {
            "mastery_score": sum(m.mastery_score * m.total_attempts for m in child_masteries) / weight_sum,
            "accuracy_score": sum(m.accuracy_score * m.total_attempts for m in child_masteries) / weight_sum,
            "consistency_score": sum(m.consistency_score * m.total_attempts for m in child_masteries) / weight_sum,
            "difficulty_score": sum(m.difficulty_score * m.total_attempts for m in child_masteries) / weight_sum,
            "speed_score": sum(m.speed_score * m.total_attempts for m in child_masteries) / weight_sum,
        }

        # Aggregate star level: median of children's star levels
        stars = sorted(m.star_level for m in child_masteries)
        n = len(stars)
        if n % 2 == 1:
            star_level = stars[n // 2]
        else:
            star_level = round((stars[n // 2 - 1] + stars[n // 2]) / 2)

        _upsert_mastery(
            db,
            user_id,
            parent.id,
            ChapterMastery(
                user_id=user_id,
                chapter_id=parent.id,
                star_level=star_level,
                mastery_score=round(agg["mastery_score"], 2),
                accuracy_score=round(agg["accuracy_score"], 2),
                consistency_score=round(agg["consistency_score"], 2),
                difficulty_score=round(agg["difficulty_score"], 2),
                speed_score=round(agg["speed_score"], 2),
                total_attempts=total_attempts,
                correct_attempts=correct_attempts,
                last_calculated_at=datetime.now(timezone.utc),
            ),
        )

    db.commit()
