"""Admin dashboard router — superadmin analytics."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.db.engine import get_db
from app.db.models import User, Subject, Question, PracticeSession, WrongBook, VocabCard, Chapter, ChapterMastery
from app.dependencies import require_admin

router = APIRouter()


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    total_users = db.query(func.count(User.id)).scalar()
    total_subjects = db.query(func.count(Subject.id)).scalar()
    total_questions = db.query(func.count(Question.id)).scalar()
    total_sessions = db.query(func.count(PracticeSession.id)).scalar()
    total_wrong = db.query(func.count(WrongBook.id)).scalar()
    total_vocab = db.query(func.count(VocabCard.id)).scalar()

    users = db.query(User).filter(User.is_active == True).all()
    user_stats = []
    for u in users:
        user_stats.append({
            "id": u.id, "username": u.username, "role": u.role,
            "subjects": db.query(func.count(Subject.id)).filter(Subject.user_id == u.id).scalar(),
            "questions": db.query(func.count(Question.id)).join(Subject).filter(Subject.user_id == u.id).scalar(),
            "sessions": db.query(func.count(PracticeSession.id)).filter(PracticeSession.user_id == u.id).scalar(),
            "wrong_entries": db.query(func.count(WrongBook.id)).filter(WrongBook.user_id == u.id).scalar(),
            "vocab_cards": db.query(func.count(VocabCard.id)).scalar(),
        })

    return {
        "totals": {"users": total_users, "subjects": total_subjects, "questions": total_questions,
                    "sessions": total_sessions, "wrong_entries": total_wrong, "vocab_cards": total_vocab},
        "users": user_stats,
    }


@router.get("/user/{user_id}")
def user_detail(user_id: int, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    user = db.query(User).filter_by(id=user_id, is_active=True).first()
    if not user: raise HTTPException(status_code=404, detail="User not found")

    subjects = (
        db.query(Subject).filter(Subject.user_id == user.id, Subject.is_active == True)
        .order_by(Subject.order_index).all()
    )

    subject_list = []
    total_chapters = 0; total_questions = 0
    for s in subjects:
        chapters = (
            db.query(Chapter).filter(Chapter.subject_id == s.id)
            .order_by(Chapter.order_index).all()
        )
        total_chapters += len(chapters)
        q_count = db.query(func.count(Question.id)).filter(Question.subject_id == s.id).scalar()
        total_questions += q_count

        # Build chapter tree with mastery
        chapter_ids = [c.id for c in chapters]
        masteries = {}
        if chapter_ids:
            records = db.query(ChapterMastery).filter(
                ChapterMastery.user_id == user.id,
                ChapterMastery.chapter_id.in_(chapter_ids)
            ).all()
            masteries = {m.chapter_id: m for m in records}

        def build_tree(nodes, parent_id=None):
            tree = []
            for n in nodes:
                if n.parent_chapter_id == parent_id:
                    m = masteries.get(n.id)
                    tree.append({
                        "id": n.id, "name": n.name, "level": n.level,
                        "is_leaf": n.is_leaf,
                        "mastery": {"star_level": m.star_level, "mastery_score": m.mastery_score} if m and n.is_leaf else None,
                        "question_count": q_count if n.is_leaf else 0,
                        "children": build_tree(nodes, n.id),
                    })
            return tree

        subject_list.append({
            "id": s.id, "name": s.name, "description": s.description,
            "chapters": build_tree(chapters),
        })

    wrong_count = db.query(func.count(WrongBook.id)).filter(WrongBook.user_id == user.id).scalar()

    return {
        "username": user.username,
        "role": user.role,
        "stats": {"subjects": len(subjects), "chapters": total_chapters,
                   "questions": total_questions, "wrongEntries": wrong_count},
        "subjects": subject_list,
    }
