"""Migrate existing SQLite content to MD vault files.

Usage:
    python -m app.vault.migrate
"""

import json
from pathlib import Path

from app.db.engine import SessionLocal
from app.db.models import Subject, Chapter, Question
from app.vault.manager import (
    ensure_vault, ensure_subject, ensure_chapter,
    write_md, add_questions_to_lesson, VAULT_ROOT,
)


def migrate():
    """One-shot migration from SQLite to vault MD files."""
    db = SessionLocal()
    try:
        subjects = db.query(Subject).filter(Subject.is_active == True).all()
        print(f"Migrating {len(subjects)} subjects...")

        for subj in subjects:
            print(f"  Subject: {subj.name}")
            ensure_subject(subj.name, subj.description or "", subj.prompt_style or "")

            # Get root chapters (no parent)
            root_chs = db.query(Chapter).filter(
                Chapter.subject_id == subj.id,
                Chapter.parent_chapter_id == None,
            ).order_by(Chapter.order_index).all()

            def migrate_chapter(ch, parent_path=""):
                if ch.is_leaf:
                    # Create lesson MD file
                    if ch.description:
                        content = ch.description
                    else:
                        content = f"# {ch.name}\n\n> （暂无讲义内容）"
                    ensure_chapter(subj.name, ch.name, ch.level, parent_path, is_leaf=True)
                    # Update content
                    from app.vault.manager import update_lesson_content
                    update_lesson_content(subj.name, ch.name, content, parent_path)

                    # Add questions
                    questions = db.query(Question).filter(
                        Question.chapter_id == ch.id
                    ).all()
                    if questions:
                        q_data = []
                        for q in questions:
                            cj = q.content_json
                            if isinstance(cj, str):
                                try:
                                    cj = json.loads(cj)
                                except json.JSONDecodeError:
                                    cj = {}
                            q_data.append({
                                "id": q.id,
                                "question_type": q.question_type,
                                "difficulty": q.difficulty,
                                "content_json": cj,
                            })
                        add_questions_to_lesson(subj.name, ch.name, q_data, parent_path)
                    print(f"    Lesson: {parent_path}/{ch.name} ({len(questions)} questions)")
                else:
                    # Create chapter folder
                    ensure_chapter(subj.name, ch.name, ch.level, parent_path, is_leaf=False)
                    new_path = f"{parent_path}/{ch.name}" if parent_path else ch.name
                    # Migrate children
                    children = db.query(Chapter).filter(
                        Chapter.parent_chapter_id == ch.id,
                    ).order_by(Chapter.order_index).all()
                    for child in children:
                        migrate_chapter(child, new_path)

            for ch in root_chs:
                migrate_chapter(ch)

        print(f"\nMigration complete! Vault at: {VAULT_ROOT}")
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
