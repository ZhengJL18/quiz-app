"""Vault manager — read/write MD files with YAML frontmatter.

Directory structure:
    data/vault/
    ├── 高等数学/                    # subject folder
    │   ├── _subject.md              # subject metadata
    │   ├── 第一章_函数与极限/         # chapter folder
    │   │   ├── _chapter.md           # chapter metadata
    │   │   ├── 1.1_映射与函数.md      # lesson (leaf chapter) = MD file
    │   │   └── 1.2_数列的极限.md
    │   └── 第二章_导数/
    └── 英语四六级/

Each .md file has YAML frontmatter with metadata, then Markdown content.
Leaf files contain both lesson content AND embedded questions.
"""

import os
import re
import shutil
import yaml
from pathlib import Path
from typing import Optional, Any

from app.config import settings

# Resolve vault root from DATABASE_URL or default
_DB_PATH = Path(settings.DATABASE_URL.replace("sqlite:///", "")) if settings.DATABASE_URL.startswith("sqlite") else Path("data/quiz.db")
VAULT_ROOT = _DB_PATH.parent / "vault"


# ── ID registry for stable vault→SQLite mapping ──
_subject_name_by_id: dict[int, str] = {}
_id_counter = [1000]


def _subject_id(name: str) -> int:
    """Get or create a stable numeric ID for a subject name."""
    for sid, sname in _subject_name_by_id.items():
        if sname == name:
            return sid
    new_id = _id_counter[0]
    _id_counter[0] += 1
    _subject_name_by_id[new_id] = name
    return new_id


def subject_name_by_id(sid: int) -> str | None:
    return _subject_name_by_id.get(sid)


def _slugify(name: str) -> str:
    """Convert a name to a safe filename."""
    return re.sub(r'[\\/:*?"<>|]', '_', name).strip()
    """Convert a name to a safe filename."""
    return re.sub(r'[\\/:*?"<>|]', '_', name).strip()


def ensure_vault() -> Path:
    """Create vault root if missing."""
    VAULT_ROOT.mkdir(parents=True, exist_ok=True)
    return VAULT_ROOT


# ── Read ──

def parse_frontmatter(path: Path) -> dict[str, Any]:
    """Parse YAML frontmatter from an MD file. Returns (meta, body)."""
    if not path.exists():
        return {}, ""
    text = path.read_text(encoding="utf-8")
    meta, body = {}, text
    if text.startswith("---\n") or text.startswith("---\r\n"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                meta = {}
            body = parts[2].strip()
    return meta, body


def write_md(path: Path, meta: dict[str, Any], body: str) -> None:
    """Write an MD file with YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml_str = yaml.dump(meta, allow_unicode=True, default_flow_style=False).strip()
    content = f"---\n{yaml_str}\n---\n\n{body.strip()}\n"
    path.write_text(content, encoding="utf-8")


# ── Subject operations ──

def list_subjects() -> list[dict]:
    """List all subjects from vault folder structure."""
    ensure_vault()
    subjects = []
    for d in sorted(VAULT_ROOT.iterdir()):
        if not d.is_dir() or d.name.startswith("_") or d.name.startswith("."):
            continue
        subject_md = d / "_subject.md"
        meta, _ = parse_frontmatter(subject_md)
        if not meta:
            # Infer from folder
            meta = {"name": d.name, "is_active": True, "order_index": 99}
        meta["id"] = _subject_id(d.name)
        meta["vault_path"] = str(d.relative_to(VAULT_ROOT))
        subjects.append(meta)
    return sorted(subjects, key=lambda s: s.get("order_index", 99))


def ensure_subject_meta(name: str, description: str = "", prompt_style: str = "") -> dict:
    """Ensure a subject exists and return its metadata dict."""
    folder = ensure_subject(name, description, prompt_style)
    return {
        "id": _subject_id(name),
        "name": name,
        "description": description,
        "prompt_style": prompt_style,
        "is_active": True,
        "order_index": 99,
        "vault_path": str(folder.relative_to(VAULT_ROOT)),
    }


def ensure_subject(name: str, description: str = "", prompt_style: str = "") -> Path:
    """Ensure a subject folder + _subject.md exists. Returns the folder path."""
    ensure_vault()
    folder = VAULT_ROOT / _slugify(name)
    folder.mkdir(parents=True, exist_ok=True)
    subject_md = folder / "_subject.md"
    if not subject_md.exists():
        write_md(subject_md, {
            "name": name,
            "description": description,
            "prompt_style": prompt_style,
            "is_active": True,
            "order_index": 99,
        }, f"# {name}\n\n{description}")
    return folder


def delete_subject(name: str) -> bool:
    """Delete a subject folder and all contents."""
    folder = VAULT_ROOT / _slugify(name)
    if folder.exists():
        shutil.rmtree(folder)
        return True
    return False


def rename_subject(old_name: str, new_name: str) -> bool:
    """Rename a subject folder."""
    old = VAULT_ROOT / _slugify(old_name)
    new = VAULT_ROOT / _slugify(new_name)
    if old.exists() and not new.exists():
        old.rename(new)
        return True
    return False


# ── Chapter / Lesson operations ──

def list_chapters(subject_name: str) -> list[dict]:
    """Recursively list all chapters/lessons under a subject."""
    folder = VAULT_ROOT / _slugify(subject_name)
    if not folder.exists():
        return []

    def walk(dir_path: Path, depth: int = 0) -> list[dict]:
        items = []
        for entry in sorted(dir_path.iterdir()):
            if entry.name.startswith("_") or entry.name.startswith("."):
                continue
            if entry.is_dir():
                ch_md = entry / "_chapter.md"
                meta, _ = parse_frontmatter(ch_md) if ch_md.exists() else ({}, "")
                if not meta:
                    meta = {"name": entry.name, "level": depth + 1, "is_leaf": False}
                meta["id"] = meta.get("id", hash(str(entry)) % 100000)
                meta["vault_path"] = str(entry.relative_to(folder))
                meta["children"] = walk(entry, depth + 1)
                items.append(meta)
            elif entry.suffix == ".md":
                meta, body = parse_frontmatter(entry)
                if not meta:
                    meta = {"name": entry.stem, "level": depth + 1, "is_leaf": True}
                meta["id"] = meta.get("id", hash(str(entry)) % 100000)
                meta["vault_path"] = str(entry.relative_to(folder))
                meta["lesson_content"] = body
                meta["children"] = []
                # Extract questions from body
                meta["question_count"] = body.count("### Q")
                items.append(meta)
        return items

    return walk(folder)


def get_lesson(subject_name: str, lesson_name: str, parent_path: str = "") -> tuple[dict, str]:
    """Get a single lesson by name. Returns (meta, body)."""
    folder = VAULT_ROOT / _slugify(subject_name)
    if parent_path:
        md_path = folder / parent_path / f"{_slugify(lesson_name)}.md"
    else:
        # Search recursively
        for md_file in folder.rglob(f"{_slugify(lesson_name)}.md"):
            md_path = md_file
            break
        else:
            return {}, ""
    return parse_frontmatter(md_path)


def ensure_chapter(subject_name: str, chapter_name: str, level: int = 1,
                   parent_path: str = "", is_leaf: bool = False) -> Path:
    """Ensure a chapter folder or MD file exists."""
    folder = VAULT_ROOT / _slugify(subject_name)
    folder.mkdir(parents=True, exist_ok=True)
    if parent_path:
        target = folder / parent_path
    else:
        target = folder
    target.mkdir(parents=True, exist_ok=True)

    if is_leaf:
        # Create a lesson MD file
        md_file = target / f"{_slugify(chapter_name)}.md"
        if not md_file.exists():
            write_md(md_file, {
                "name": chapter_name,
                "level": level,
                "is_leaf": True,
            }, f"# {chapter_name}\n\n> 讲义生成中...")
        return md_file
    else:
        # Create a chapter folder with _chapter.md
        ch_dir = target / _slugify(chapter_name)
        ch_dir.mkdir(parents=True, exist_ok=True)
        ch_md = ch_dir / "_chapter.md"
        if not ch_md.exists():
            write_md(ch_md, {
                "name": chapter_name,
                "level": level,
                "is_leaf": False,
            }, f"# {chapter_name}")
        return ch_dir


def delete_chapter(subject_name: str, chapter_name: str, parent_path: str = "") -> bool:
    """Delete a chapter folder or MD file."""
    folder = VAULT_ROOT / _slugify(subject_name)
    if parent_path:
        target = folder / parent_path / _slugify(chapter_name)
    else:
        target = folder / _slugify(chapter_name)
    # Try as folder
    if target.is_dir():
        shutil.rmtree(target)
        return True
    # Try as MD file
    md_file = target.with_suffix(".md") if target.suffix != ".md" else target
    if md_file.exists():
        md_file.unlink()
        return True
    return False


def update_lesson_content(subject_name: str, lesson_name: str, content: str, parent_path: str = "") -> bool:
    """Update lesson content in the MD file."""
    folder = VAULT_ROOT / _slugify(subject_name)
    if parent_path:
        md_path = folder / parent_path / f"{_slugify(lesson_name)}.md"
    else:
        for md_file in folder.rglob(f"{_slugify(lesson_name)}.md"):
            md_path = md_file
            break
        else:
            return False
    if not md_path.exists():
        return False
    meta, _ = parse_frontmatter(md_path)
    # Preserve question section if body has it
    _, old_body = parse_frontmatter(md_path)
    q_section = ""
    if "## 练习题" in old_body:
        q_section = "\n\n" + old_body.split("## 练习题", 1)[1]
    write_md(md_path, meta, content.strip() + q_section)
    return True


def add_questions_to_lesson(subject_name: str, lesson_name: str, questions: list[dict], parent_path: str = "") -> bool:
    """Append questions to a lesson MD file."""
    folder = VAULT_ROOT / _slugify(subject_name)
    if parent_path:
        md_path = folder / parent_path / f"{_slugify(lesson_name)}.md"
    else:
        for md_file in folder.rglob(f"{_slugify(lesson_name)}.md"):
            md_path = md_file
            break
        else:
            return False
    meta, body = parse_frontmatter(md_path)

    # Build question section
    q_lines = ["\n## 练习题\n"]
    for i, q in enumerate(questions, 1):
        q_type = q.get("question_type", "single_choice")
        cj = q.get("content_json", {})
        if isinstance(cj, str):
            import json as _json
            cj = _json.loads(cj)
        q_text = cj.get("question_text", str(q.get("id", "?")))
        q_lines.append(f"### Q{i} ({q_type})")
        q_lines.append(f"{q_text}\n")
        if q_type == "single_choice":
            opts = cj.get("options", {})
            if isinstance(opts, list):
                opts = {chr(65 + i): v for i, v in enumerate(opts)}
            correct = cj.get("correct_answer", "")
            for k, v in opts.items():
                marker = "x" if k == correct else " "
                q_lines.append(f"- [{marker}] {k}. {v}")
        elif q_type == "multiple_choice":
            opts = cj.get("options", {})
            if isinstance(opts, list):
                opts = {chr(65 + i): v for i, v in enumerate(opts)}
            corrects = cj.get("correct_answers", [])
            if isinstance(corrects, str):
                import json as _json
                corrects = _json.loads(corrects)
            for k, v in opts.items():
                marker = "x" if k in corrects else " "
                q_lines.append(f"- [{marker}] {k}. {v}")
        elif q_type == "fill_blank":
            answers = cj.get("correct_answers", cj.get("correct_answer", ""))
            q_lines.append(f"答案：{answers}")
        q_lines.append("")

    write_md(md_path, meta, body.strip() + "\n" + "\n".join(q_lines))
    return True
