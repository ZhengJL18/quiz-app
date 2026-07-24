"""Migrate Note.content from DB to vault files. DB stores path pointer."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.db.engine import SessionLocal
from app.db.models import Note
from app.services.vault_manager import get_vault

db = SessionLocal()
notes = db.query(Note).filter(Note.content.isnot(None), Note.content != '').all()
migrated = 0

for note in notes:
    content = note.content.strip()
    if content.startswith('notes/'):
        continue  # Already migrated

    vault = get_vault(note.user_id)
    vault_path = f"notes/{note.id}.md"
    vault.write(vault_path, content)
    note.content = vault_path
    migrated += 1

db.commit()
db.close()
print(f"Migrated: {migrated} notes")
