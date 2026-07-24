"""Agent Context Assembler — intelligent context building using MemoryManager.

Unlike the old version that just dumped all files into the prompt,
this version uses the MemoryManager to retrieve the most relevant memories
for the current learning context, and structures them for maximum usefulness.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from app.services.vault_manager import VaultManager
from app.services.memory_writer import MemoryManager, get_weaknesses, get_relevant_memories

MAX_TOKENS = 30_000
TOKEN_RESERVE = 5_000


def estimate_tokens(text: str) -> int:
    """Rough token estimate: Chinese ~0.5 tokens/char, English ~0.25 tokens/char."""
    chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other = len(text) - chinese
    return int(chinese * 0.5 + other * 0.25)


def build_agent_context(
    vault: VaultManager,
    skill_prompt: str | None = None,
    current_subject: str | None = None,
    current_chapter: str | None = None,
    current_concept: str | None = None,
) -> str:
    """Assemble an intelligent system prompt for an Agent call.
    
    Priority order (with intelligent retrieval):
    1. Skill prompt (if matched by router) — highest priority
    2. Student profile (goals, preferences, learning style)
    3. Current context: subject, chapter, concept being discussed
    4. Relevant weaknesses (from MemoryManager, sorted by weight)
    5. Recent high-weight memories (from MemoryManager, relevance-scored)
    6. Recent journal entries (last 3 days)
    7. Knowledge summary for current subject
    """
    budget = MAX_TOKENS - TOKEN_RESERVE
    parts = []
    token_usage = 0
    skipped = []

    def add(text: str, label: str, priority: int):
        nonlocal token_usage
        if not text or not text.strip():
            return
        t = estimate_tokens(text)
        if token_usage + t <= budget:
            parts.append(text)
            token_usage += t
        else:
            skipped.append((priority, label))

    # ═══ Tier 1: Identity / Skill ═══
    if skill_prompt:
        add(skill_prompt, "skill_prompt", 1)
    else:
        system_md = vault.read("system/system.md") or ""
        if system_md:
            add(system_md, "system.md", 1)
        else:
            # Fallback identity
            add(
                "# 三一学习助手\n\n"
                "你是三一学习Agent。你的角色是一个认识学生、懂教育、会推动成长的AI学习教练。\n\n"
                "## 核心原则\n"
                "1. 主动了解学生：不了解就问，不要假装了解\n"
                "2. 推动练习：出题 > 讲解 > 闲聊。每次对话结尾，提案下一步做什么\n"
                "3. 个性化：根据学生的掌握度、薄弱点、学习风格调整教学\n"
                "4. 记忆驱动：每次交互前回顾学生的记忆文件\n",
                "fallback_identity", 1
            )

    # ═══ Tier 2: Student Profile ═══
    profile_parts = []
    for f in ["goals.md", "preferences.md", "context.md"]:
        c = vault.read(f"profile/{f}")
        if c:
            profile_parts.append(c.strip())
    if profile_parts:
        profile_text = "\n\n".join(profile_parts)
        add(f"## 学生画像\n\n{profile_text}", "profile", 2)

    # ═══ Tier 3: Current Learning Context ═══
    if current_subject or current_chapter or current_concept:
        context_lines = ["## 当前学习上下文"]
        if current_subject:
            context_lines.append(f"- 科目: {current_subject}")
        if current_chapter:
            context_lines.append(f"- 章节: {current_chapter}")
            # Try to get chapter-specific context from knowledge
            chapter_content = vault.read(f"knowledge/{current_subject}/{current_chapter}/_context.md")
            if chapter_content:
                context_lines.append(f"\n{chapter_content[:1000]}")
        if current_concept:
            context_lines.append(f"- 正在讨论的概念: {current_concept}")
        add("\n".join(context_lines), "learning_context", 3)

    # ═══ Tier 4: Relevant Weaknesses (from MemoryManager) ═══
    weaknesses = get_weaknesses(vault, subject=current_subject)
    if weaknesses:
        weak_text = "## ⚠️ 已知薄弱点\n\n"
        for w in weaknesses[:5]:
            weak_text += f"- [{w.get('weight', 3)}/5] {w.get('summary', '')}\n"
        add(weak_text, "weaknesses", 4)

    # ═══ Tier 5: Relevant Memories (from MemoryManager) ═══
    memories = get_relevant_memories(
        vault,
        subject=current_subject,
        chapter=current_chapter,
        concept=current_concept,
        limit=10,
    )
    if memories:
        mem_text = "## 🧠 相关记忆\n\n"
        for mem in memories:
            mem_text += f"- [{mem.get('weight', 3)}/5] {mem.get('summary', '')} ({mem.get('source', '')})\n"
        add(mem_text, "memories", 5)

    # ═══ Tier 6: Recent Journal (last 3 days) ═══
    journal_entries = _get_recent_journal(vault, days=3)
    if journal_entries:
        journal_text = "\n\n".join(journal_entries)
        add(f"## 📅 最近学习日志\n\n{journal_text}", "journal", 6)

    # ═══ Tier 7: Knowledge Summary for current subject ═══
    if current_subject:
        knowledge_summary = vault.read(f"knowledge/{current_subject}/_summary.md") or ""
        if not knowledge_summary:
            knowledge_summary = vault.read(f"knowledge/{current_subject}/index.md") or ""
        if knowledge_summary:
            add(f"## 📚 {current_subject} 知识概览\n\n{knowledge_summary[:2000]}", "knowledge_summary", 7)

    # ═══ Tier 8: Learning Stats ═══
    mgr = MemoryManager(vault)
    stats = mgr.get_streak_and_stats()
    if stats.get("streak_days", 0) > 0 or stats.get("recent_dates"):
        stats_text = "## 📊 学习统计\n\n"
        if stats.get("streak_days", 0) > 0:
            stats_text += f"- 🔥 连续学习: {stats['streak_days']} 天\n"
        if stats.get("recent_dates"):
            stats_text += f"- 最近学习: {', '.join(stats['recent_dates'][:3])}\n"
        add(stats_text, "stats", 8)

    # ═══ Assemble ═══
    context = "\n\n---\n\n".join(parts)

    # Hint for thin context
    if token_usage < 2000:
        context += (
            "\n\n[认知状态: 你对这个学生还不太了解。"
            "主动问学生关于ta的学习目标、当前困难、学习习惯。"
            "建立认知画像是最优先的事——不了解学生就不要乱给建议。]"
        )

    if skipped:
        skipped_list = ", ".join(f"{label}(P{pri})" for pri, label in sorted(skipped))
        context += f"\n\n[Context: {token_usage}/{budget} tokens. 为避免超限已跳过: {skipped_list}]"

    return context


def _get_recent_journal(vault: VaultManager, days: int = 3) -> list[str]:
    """Get journal entries from the last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    entries = []
    journal_dir = vault.root / "journal"
    if not journal_dir.exists():
        return entries
    for f in sorted(journal_dir.iterdir(), reverse=True):
        if f.suffix == ".md":
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                if mtime >= cutoff.replace(tzinfo=timezone.utc):
                    content = f.read_text(encoding="utf-8", errors="replace")
                    entries.append(f"### {f.stem}\n\n{content[:1500]}")
            except Exception:
                pass
        if len(entries) >= days:
            break
    return entries
