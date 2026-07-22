"""Memory Writer — Agent self-learning: updates vault files after each interaction."""

from datetime import datetime, timezone
from app.services.vault_manager import VaultManager


def record_practice_session(vault: VaultManager, session_data: dict):
    """Write a practice session record to the vault.

    session_data should contain:
    - session_id, subject_name, chapter_name, mode
    - questions: list of {type, user_answer, correct_answer, is_correct, time_spent}
    - score, max_score
    """
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    session_id = session_data.get("session_id", "???")
    filename = f"practice/sessions/{date_str}-{session_id}.md"

    lines = [
        f"---",
        f"session_id: {session_id}",
        f"mode: {session_data.get('mode', 'unknown')}",
        f"subject: {session_data.get('subject_name', '')}",
        f"chapter: {session_data.get('chapter_name', '')}",
        f"score: {session_data.get('score', 0)}/{session_data.get('max_score', 0)}",
        f"date: {date_str}",
        f"---",
        "",
        f"# {session_data.get('chapter_name', '练习')} · 练习记录",
        "",
    ]

    for i, q in enumerate(session_data.get("questions", [])):
        status = "✅" if q.get("is_correct") else "❌" if q.get("is_correct") is False else "⏳"
        lines.append(f"## Q{i+1} · {q.get('type', 'unknown')} · {status}")
        lines.append(f"题目: {q.get('question_text', '?')[:200]}")
        lines.append(f"你的答案: {q.get('user_answer', '')[:200]}")
        if q.get("correct_answer"):
            lines.append(f"正确答案: {str(q.get('correct_answer'))[:200]}")
        lines.append(f"用时: {q.get('time_spent', 0)}s")
        lines.append("")

    lines.append(f"## 本轮总结")
    lines.append(f"- 正确率: {session_data.get('score', 0)}/{session_data.get('max_score', 0)}")
    lines.append("")

    vault.write(filename, "\n".join(lines))


def update_mastery(vault: VaultManager, subject_name: str, chapter_name: str, total: int, correct: int):
    """Update mastery.md for a subject after a practice round."""
    mastery_path = f"讲义/{subject_name}/mastery.md"
    existing = vault.read(mastery_path) or f"---\nsubject: {subject_name}\nupdated: {datetime.now(timezone.utc).isoformat()}\n---\n\n# 掌握度矩阵\n\n"

    # Simple append of this round's data
    pct = f"{int(correct / total * 100)}%" if total > 0 else "0%"
    entry = f"- {chapter_name} · 最近一轮: {correct}/{total} ({pct}) · {datetime.now(timezone.utc).strftime('%H:%M')}"

    vault.write(mastery_path, existing.rstrip() + "\n" + entry + "\n")


def write_journal_entry(vault: VaultManager, summary: str):
    """Append a daily journal entry."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = f"日志/{date_str}.md"
    timestamp = datetime.now(timezone.utc).strftime("%H:%M")

    existing = vault.read(path) or f"---\ndate: {date_str}\n---\n\n# 学习日志 · {date_str}\n\n"
    entry = f"\n**{timestamp}** · {summary}\n"
    vault.write(path, existing.rstrip() + entry)


def append_memory(vault: VaultManager, insight: str, weight: int = 3):
    """Add a new cognitive insight to 系统/memory.md with a weight (1-5)."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    entry = f"\n--- weight: {weight}\n**{timestamp}** · {insight}\n"
    vault.append("系统/memory.md", entry)


def archive_low_weight_memories(vault: VaultManager):
    """Weekly: move weight ≤2 entries to memory-archive.md."""
    memory = vault.read("系统/memory.md") or ""
    lines = memory.split("\n")
    kept = []
    archived = []
    current_entry = []
    current_weight = 5

    for line in lines:
        if line.startswith("--- weight:"):
            # Flush previous entry
            entry = "\n".join(current_entry)
            if current_weight <= 2:
                archived.append(entry)
            else:
                kept.append(entry)
            current_entry = []
            try:
                current_weight = int(line.split(":")[1].strip())
            except ValueError:
                current_weight = 5
        current_entry.append(line)

    # Flush last entry
    entry = "\n".join(current_entry)
    if current_weight <= 2:
        archived.append(entry)
    else:
        kept.append(entry)

    if archived:
        archive_content = vault.read("系统/memory-archive.md") or "# 记忆归档\n\n"
        archive_content += "\n---\n" + "\n".join(archived)
        vault.write("系统/memory-archive.md", archive_content)
        vault.write("系统/memory.md", "\n".join(kept))
