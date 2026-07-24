"""Migrate existing lesson content from DB to vault files.
Replaces Chapter.description (full text) with vault path (knowledge/...).
Safe to run multiple times — skips already-migrated chapters.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.db.engine import SessionLocal
from app.db.models import Chapter, Subject
from app.services.vault_manager import get_vault

db = SessionLocal()
chapters = db.query(Chapter).filter(Chapter.description.isnot(None), Chapter.description != '').all()
migrated = 0
skipped = 0

for ch in chapters:
    desc = ch.description.strip()
    # Skip if already a vault path
    if desc.startswith('knowledge/'):
        skipped += 1
        continue

    subject = db.query(Subject).filter_by(id=ch.subject_id).first()
    if not subject:
        continue

    safe_subj = "".join(c for c in subject.name if c.isalnum() or c in " _-（）()").strip()
    safe_ch = "".join(c for c in ch.name if c.isalnum() or c in " _-（）()").strip()
    vault_path = f"knowledge/{safe_subj}/{safe_ch}.md"

    vault = get_vault(subject.user_id)
    vault.write(vault_path, desc)
    ch.description = vault_path
    migrated += 1

db.commit()
db.close()
print(f"Migrated: {migrated}, Skipped: {skipped}")
