"""Rename chapter dirs with order-index prefixes for correct sorting.

Before:
  knowledge/高等数学/第一章 函数与极限/极限.md

After:
  knowledge/高等数学/01_第一章 函数与极限/极限.md
"""
import sys, os, shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.engine import SessionLocal
from app.db.models import Chapter, Subject

VAULT_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "users"

def migrate():
    db = SessionLocal()

    for user_dir in sorted(VAULT_ROOT.glob("*")):
        if not user_dir.is_dir() or not user_dir.name.isdigit():
            continue
        kdir = user_dir / "knowledge"
        if not kdir.exists():
            continue

        for subj_dir in sorted(kdir.iterdir()):
            if not subj_dir.is_dir():
                continue

            # Find level-1 chapters for this subject
            subj = db.query(Subject).filter_by(name=subj_dir.name).first()
            if not subj:
                continue

            parent_chapters = db.query(Chapter).filter_by(
                subject_id=subj.id, parent_chapter_id=None
            ).order_by(Chapter.order_index).all()

            if not parent_chapters:
                continue

            print(f"\n[{user_dir.name}] {subj.name}")

            # Build rename map: old_name → new_name with order prefix
            renames = {}
            for ch in parent_chapters:
                old_name = ch.name
                new_name = f"{ch.order_index:02d}_{ch.name}"
                if old_name != new_name:
                    renames[old_name] = new_name

            # Execute renames
            for old_name, new_name in renames.items():
                old_dir = subj_dir / old_name
                new_dir = subj_dir / new_name
                if old_dir.exists() and not new_dir.exists():
                    shutil.move(str(old_dir), str(new_dir))
                    print(f"  {old_name}/ → {new_name}/")

            # Also handle level-2 subdirectories (节)
            for ch in parent_chapters:
                new_ch_name = f"{ch.order_index:02d}_{ch.name}"
                ch_dir = subj_dir / new_ch_name
                if not ch_dir.exists():
                    continue
                l2_chapters = db.query(Chapter).filter_by(
                    parent_chapter_id=ch.id
                ).order_by(Chapter.order_index).all()
                for l2 in l2_chapters:
                    old_l2 = ch_dir / l2.name
                    new_l2 = ch_dir / f"{l2.order_index:02d}_{l2.name}"
                    if old_l2.exists() and not new_l2.exists():
                        shutil.move(str(old_l2), str(new_l2))
                        print(f"    {l2.name}/ → {l2.order_index:02d}_{l2.name}/")

            # Update all DB pointers for this user's chapters in this subject
            updated = 0
            all_chapters = db.query(Chapter).filter_by(subject_id=subj.id).all()
            for ch in all_chapters:
                desc = ch.description or ""
                if "knowledge/" in desc and "/" in desc:
                    # Rebuild the pointer with new names
                    for old_name, new_name in renames.items():
                        if f"/{old_name}/" in desc:
                            desc = desc.replace(f"/{old_name}/", f"/{new_name}/")
                            updated += 1
                    ch.description = desc

            if updated:
                print(f"  Updated {updated} DB pointers")

    db.commit()
    db.close()
    print("\nDone.")

if __name__ == "__main__":
    migrate()
