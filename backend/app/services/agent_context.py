"""Agent Context Assembler — builds the system prompt from vault files."""

from app.services.vault_manager import VaultManager

MAX_TOKENS = 30_000
TOKEN_RESERVE = 5_000


def estimate_tokens(text: str) -> int:
    """Rough token estimate: Chinese ~0.5 tokens/char, English ~0.25 tokens/char."""
    chinese = sum(1 for c in text if '一' <= c <= '鿿')
    other = len(text) - chinese
    return int(chinese * 0.5 + other * 0.25)


def build_agent_context(vault: VaultManager, skill_prompt: str | None = None) -> str:
    """Assemble the full system prompt for an Agent call.

    Priority order:
    1. Skill prompt (if matched) — replaces default system.md
    2. 系统/system.md (default identity)
    3. 系统/memory.md (long-term memory, recent high-weight items)
    4. 画像/ (goals, preferences)
    5. 讲义/{科目}/_summary.md (knowledge overview)
    6. practice/stats.md (practice statistics)
    7. 日志/ last 3 days
    """
    budget = MAX_TOKENS - TOKEN_RESERVE
    parts = []
    token_usage = 0
    skipped = []

    def add(text: str, label: str, priority: int):
        nonlocal token_usage
        if not text.strip():
            return
        t = estimate_tokens(text)
        if token_usage + t <= budget:
            parts.append(text)
            token_usage += t
        else:
            skipped.append((priority, label))

    # Priority tier 1: Identity
    if skill_prompt:
        add(skill_prompt, "skill_prompt", 1)
    else:
        system_md = vault.read("系统/system.md") or ""
        add(system_md, "system.md", 1)

    # Priority tier 2: Memory (only high-weight items)
    memory = vault.read("系统/memory.md") or ""
    # Keep only recent high-weight entries (weight 3-5)
    memory_filtered = _filter_memory(memory)
    add(memory_filtered, "memory.md", 2)

    # Priority tier 3: Profile
    profile_parts = []
    for f in ["goals.md", "preferences.md", "context.md"]:
        c = vault.read(f"画像/{f}")
        if c:
            profile_parts.append(c)
    add("\n\n".join(profile_parts), "profile", 3)

    # Priority tier 4: Knowledge summaries
    knowledge_summary = vault.read("讲义/_summary.md")
    if not knowledge_summary:
        knowledge_summary = vault.read("讲义/index.md")
    add(knowledge_summary or "", "knowledge", 4)

    # Priority tier 5: Practice stats
    stats = vault.read("practice/stats.md") or ""
    add(stats, "practice_stats", 5)

    # Priority tier 6: Recent journal (last 3 days)
    journal_entries = _get_recent_journal(vault, days=3)
    add("\n\n".join(journal_entries), "journal_recent", 6)

    # Build final prompt
    context = "\n\n---\n\n".join(parts)

    # Hint: if context is very thin, the agent doesn't know the student yet
    if token_usage < 2000:
        context += (
            "\n\n[认知状态: 你对这个学生的了解还很有限。"
            "主动问学生关于ta的目标、学习习惯、近期困难——建立认知是最优先的事。"
            "不要假装了解ta。]"
        )

    if skipped:
        skipped_list = ", ".join(f"{label}(P{pri})" for pri, label in sorted(skipped))
        context += f"\n\n[Context Budget: {token_usage}/{budget} tokens used. Skipped: {skipped_list}]"

    return context


def _filter_memory(memory: str) -> str:
    """Keep only high-weight (≥3) entries from memory.md. Low-weight items are archived."""
    lines = memory.split("\n")
    output = []
    in_low_weight = False
    for line in lines:
        if line.startswith("weight:") or line.startswith("--- weight:"):
            try:
                w = int(line.split(":")[1].strip())
                in_low_weight = w < 3
            except ValueError:
                in_low_weight = False
        if not in_low_weight:
            output.append(line)
    return "\n".join(output)


def _get_recent_journal(vault: VaultManager, days: int = 3) -> list[str]:
    """Get journal entries from the last N days."""
    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    entries = []
    journal_dir = vault.root / "日志"
    if not journal_dir.exists():
        return entries
    for f in sorted(journal_dir.iterdir(), reverse=True):
        if f.suffix == ".md" and f.stat().st_mtime >= cutoff.timestamp():
            try:
                entries.append(f.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                pass
        if len(entries) >= days:
            break
    return entries
