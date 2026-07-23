"""Memory Manager — Active learning system: extracts patterns, tracks mastery decay, auto-adjusts weights.

Design principles (modeled after Hermes agent memory):
1. Every interaction produces structured insights, not just logs
2. Memory weights auto-adjust based on actual performance
3. Cross-referencing: weak foundations detected from error patterns
4. Decay tracking: concepts not practiced recently get flagged
"""

from datetime import datetime, timezone, timedelta
from collections import defaultdict
import json
import re
from pathlib import Path
from typing import Optional

from app.services.vault_manager import VaultManager


# ── Insight types ──

class InsightType:
    WEAKNESS = "weakness"           # Consistently wrong
    STRENGTH = "strength"           # Consistently correct  
    PATTERN = "pattern"             # Recurring error pattern
    FOUNDATION = "foundation"       # Foundational gap discovered
    PROGRESS = "progress"           # Notable improvement
    SPEED = "speed"                 # Time-related insight
    CONCEPT_LINK = "concept_link"   # Connection between concepts


class MemoryManager:
    """Active memory system that learns from every interaction."""

    def __init__(self, vault: VaultManager):
        self.vault = vault
        self._insights_cache = None

    # ═══ Writing: Extract insights from interactions ═══

    def learn_from_practice(self, session_data: dict):
        """Extract learning insights from a completed practice session.
        
        This is the core active-learning function. After every practice round,
        it analyzes what happened and writes structured insights.
        """
        now = datetime.now(timezone.utc)
        subject = session_data.get("subject_name", "")
        chapter = session_data.get("chapter_name", "")
        
        # 1. Record the session (keep the original logging)
        self._write_session_log(session_data, now)
        
        # 2. Analyze question-level performance
        insights = self._analyze_questions(session_data, subject, chapter, now)
        
        # 3. Check for concept decay (haven't practiced recently)
        decay_insights = self._check_decay(subject, chapter, now)
        insights.extend(decay_insights)
        
        # 4. Update mastery tracking
        self._update_mastery_tracking(session_data, now)
        
        # 5. Write all insights to memory
        for insight in insights:
            self._write_insight(insight)
        
        # 6. Update daily journal summary
        self._write_daily_summary(session_data, insights, now)
        
        return insights

    def learn_from_chat(self, user_message: str, agent_response: str, context: dict = None):
        """Extract insights from an AI chat interaction."""
        now = datetime.now(timezone.utc)
        insights = []
        
        # Detect if user asked about a concept they're struggling with
        struggle_patterns = [
            (r"(?:不懂|不明白|不会|太难|搞不懂|理解不了)(.+?)(?:了|啊|呢|$)", "struggle"),
            (r"(?:什么是|什么叫|怎么理解)(.+?)(?:\?|？|$)", "concept_question"),
            (r"(?:帮我|给我)(?:讲讲|解释|说说)(.+?)(?:$|\?|？)", "explain_request"),
        ]
        
        for pattern, ptype in struggle_patterns:
            match = re.search(pattern, user_message)
            if match:
                concept = match.group(1).strip()[:50]
                insight = {
                    "type": InsightType.WEAKNESS if ptype == "struggle" else InsightType.PATTERN,
                    "subject": context.get("subject_name", "") if context else "",
                    "concept": concept,
                    "weight": 4 if ptype == "struggle" else 3,
                    "timestamp": now.isoformat(),
                    "summary": f"对「{concept}」有理解困难（{ptype}）",
                    "source": "chat",
                }
                insights.append(insight)
        
        for insight in insights:
            self._write_insight(insight)
        
        return insights

    def learn_from_reflect(self, reflection_data: dict):
        """Learn from a post-practice reflection session."""
        insights = []
        now = datetime.now(timezone.utc)
        
        # Extract self-identified weaknesses
        if reflection_data.get("struggled_with"):
            for item in reflection_data["struggled_with"]:
                insights.append({
                    "type": InsightType.WEAKNESS,
                    "subject": reflection_data.get("subject_name", ""),
                    "concept": item,
                    "weight": 5,  # Self-reported = high weight
                    "timestamp": now.isoformat(),
                    "summary": f"自评薄弱点：{item}",
                    "source": "reflect",
                })
        
        for insight in insights:
            self._write_insight(insight)
        
        return insights

    # ═══ Reading: Retrieve relevant context ═══

    def get_relevant_memories(self, subject: str = None, chapter: str = None, 
                              concept: str = None, limit: int = 10) -> list[dict]:
        """Get the most relevant memories for the current context.
        
        Ranking: weight × recency_factor × relevance_factor
        """
        all_insights = self._load_all_insights()
        now = datetime.now(timezone.utc)
        scored = []
        
        for ins in all_insights:
            score = ins.get("weight", 3)
            
            # Recency boost (exponential decay, half-life 7 days)
            try:
                ts = datetime.fromisoformat(ins["timestamp"])
                days_ago = (now - ts).total_seconds() / 86400
                score *= max(0.1, 2 ** (-days_ago / 7))
            except (KeyError, ValueError):
                pass
            
            # Relevance boost
            relevance = 0
            if subject and ins.get("subject") == subject:
                relevance += 3
            if chapter and ins.get("chapter") == chapter:
                relevance += 5
            if concept and concept in ins.get("concept", ""):
                relevance += 10
            score *= (1 + relevance * 0.5)
            
            scored.append((score, ins))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ins for _, ins in scored[:limit]]

    def get_weaknesses(self, subject: str = None) -> list[dict]:
        """Get all known weaknesses, optionally filtered by subject."""
        all_insights = self._load_all_insights()
        weaknesses = [
            ins for ins in all_insights
            if ins.get("type") in (InsightType.WEAKNESS, InsightType.FOUNDATION)
        ]
        if subject:
            weaknesses = [w for w in weaknesses if w.get("subject") == subject]
        
        # Sort by weight (higher = more important)
        weaknesses.sort(key=lambda x: x.get("weight", 3), reverse=True)
        return weaknesses

    def get_concept_map(self) -> dict:
        """Build a concept relationship map from insights."""
        insights = self._load_all_insights()
        concepts = defaultdict(list)
        
        for ins in insights:
            if ins.get("type") == InsightType.CONCEPT_LINK:
                concepts[ins.get("source_concept", "")].append(ins.get("target_concept", ""))
            if ins.get("concept"):
                concepts[ins.get("subject", "general")].append(ins.get("concept", ""))
        
        return dict(concepts)

    def get_streak_and_stats(self) -> dict:
        """Get learning streak and statistics."""
        journal_dir = self.vault.root / "journal"
        if not journal_dir.exists():
            return {"streak_days": 0, "total_sessions": 0, "total_questions": 0}
        
        dates = []
        total_sessions = 0
        
        for f in sorted(journal_dir.glob("*.md"), reverse=True):
            try:
                dates.append(datetime.strptime(f.stem, "%Y-%m-%d").date())
            except ValueError:
                continue
        
        # Calculate streak
        streak = 0
        today = datetime.now(timezone.utc).date()
        for d in dates:
            if d == today - timedelta(days=streak):
                streak += 1
            else:
                break
        
        return {
            "streak_days": streak,
            "total_sessions": total_sessions,
            "recent_dates": [d.isoformat() for d in dates[:7]],
        }

    # ═══ Internal helpers ═══

    def _analyze_questions(self, session_data, subject, chapter, now) -> list[dict]:
        """Extract insights from individual question performance."""
        insights = []
        questions = session_data.get("questions", [])
        
        if not questions:
            return insights
        
        correct = sum(1 for q in questions if q.get("is_correct"))
        total = len(questions)
        accuracy = correct / total if total > 0 else 0
        
        # Pattern 1: Overall weakness in this chapter
        if accuracy < 0.4 and total >= 3:
            insights.append({
                "type": InsightType.WEAKNESS,
                "subject": subject,
                "chapter": chapter,
                "concept": chapter,
                "weight": 5,
                "timestamp": now.isoformat(),
                "summary": f"「{chapter}」整体正确率仅{int(accuracy*100)}%（{correct}/{total}）",
                "source": "practice",
                "accuracy": accuracy,
                "total_questions": total,
            })
        
        # Pattern 2: Notable strength
        if accuracy >= 0.8 and total >= 3:
            insights.append({
                "type": InsightType.STRENGTH,
                "subject": subject,
                "chapter": chapter,
                "concept": chapter,
                "weight": 3,
                "timestamp": now.isoformat(),
                "summary": f"「{chapter}」掌握良好，正确率{int(accuracy*100)}%",
                "source": "practice",
                "accuracy": accuracy,
            })
        
        # Pattern 3: Speed analysis
        times = [q.get("time_spent", 0) for q in questions]
        avg_time = sum(times) / len(times) if times else 0
        if avg_time > 120 and total >= 3:  # Avg > 2 min per question
            insights.append({
                "type": InsightType.SPEED,
                "subject": subject,
                "chapter": chapter,
                "weight": 2,
                "timestamp": now.isoformat(),
                "summary": f"「{chapter}」平均答题时间{int(avg_time)}秒，可能需要提升熟练度",
                "source": "practice",
            })
        
        # Pattern 4: Specific question types consistently wrong
        type_stats = defaultdict(lambda: {"correct": 0, "total": 0})
        for q in questions:
            qtype = q.get("type", "unknown")
            type_stats[qtype]["total"] += 1
            if q.get("is_correct"):
                type_stats[qtype]["correct"] += 1
        
        for qtype, stats in type_stats.items():
            if stats["total"] >= 2:
                type_acc = stats["correct"] / stats["total"]
                if type_acc < 0.3:
                    insights.append({
                        "type": InsightType.WEAKNESS,
                        "subject": subject,
                        "chapter": chapter,
                        "concept": f"{chapter}-{qtype}",
                        "weight": 4,
                        "timestamp": now.isoformat(),
                        "summary": f"「{chapter}」的{qtype}题型正确率仅{int(type_acc*100)}%",
                        "source": "practice",
                    })
        
        return insights

    def _check_decay(self, subject, chapter, now) -> list[dict]:
        """Check if concepts haven't been practiced recently."""
        insights = []
        mastery_path = f"knowledge/{subject}/mastery.md"
        content = self.vault.read(mastery_path)
        
        if not content:
            return insights
        
        # Check when this chapter was last practiced
        chapter_marker = f"| {chapter} |"
        if chapter_marker in content:
            # Extract last practice date from mastery.md
            for line in content.split("\n"):
                if chapter_marker in line and "last_practice" in line:
                    try:
                        date_str = line.split("last_practice:")[-1].strip()
                        last_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        days_gap = (now.replace(tzinfo=None) - last_date.replace(tzinfo=None)).days
                        if days_gap > 7:
                            insights.append({
                                "type": InsightType.PATTERN,
                                "subject": subject,
                                "chapter": chapter,
                                "concept": chapter,
                                "weight": 3,
                                "timestamp": now.isoformat(),
                                "summary": f"「{chapter}」已{days_gap}天未练习，可能出现遗忘",
                                "source": "decay_check",
                            })
                    except (ValueError, IndexError):
                        pass
                    break
        
        return insights

    def _update_mastery_tracking(self, session_data, now):
        """Update the structured mastery tracking file."""
        subject = session_data.get("subject_name", "")
        chapter = session_data.get("chapter_name", "")
        questions = session_data.get("questions", [])
        
        if not subject:
            return
        
        total = len(questions)
        correct = sum(1 for q in questions if q.get("is_correct"))
        accuracy = correct / total if total > 0 else 0
        
        path = f"knowledge/{subject}/mastery.md"
        content = self.vault.read(path) or ""
        
        # Create or update chapter row in mastery table
        chapter_row = f"| {chapter} | {int(accuracy*100)}% | {correct}/{total} | {now.strftime('%Y-%m-%d %H:%M')} |"
        
        if f"| {chapter} |" in content:
            # Update existing row
            lines = content.split("\n")
            new_lines = []
            for line in lines:
                if f"| {chapter} |" in line:
                    new_lines.append(chapter_row)
                else:
                    new_lines.append(line)
            content = "\n".join(new_lines)
        else:
            # Append new row
            if "| 章节 |" not in content:
                content += "\n\n| 章节 | 掌握度 | 最近一轮 | 最后练习 |\n|------|--------|----------|----------|\n"
            content += chapter_row + "\n"
        
        self.vault.write(path, content)

    def _write_session_log(self, session_data, now):
        """Write the raw practice session log (kept for reference)."""
        date_str = now.strftime("%Y-%m-%d")
        session_id = session_data.get("session_id", "???")
        path = f"practice/sessions/{date_str}-{session_id}.md"
        
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
            status = "✅" if q.get("is_correct") else "❌"
            lines.append(f"## Q{i+1} · {q.get('type', 'unknown')} · {status}")
            lines.append(f"题目: {q.get('question_text', '?')[:200]}")
            if q.get("user_answer"):
                lines.append(f"答案: {str(q.get('user_answer'))[:200]}")
            lines.append(f"用时: {q.get('time_spent', 0)}s")
            lines.append("")
        
        self.vault.write(path, "\n".join(lines))

    def _write_insight(self, insight: dict):
        """Write a single insight to the memory index."""
        path = "system/memory-index.json"
        insights = self._load_all_insights()
        insights.append(insight)
        
        # Keep only last 200 insights
        if len(insights) > 200:
            # Archive old ones
            old = insights[:-200]
            archive_path = "system/memory-archive.json"
            archived = self._load_archive() + old
            self.vault.write(archive_path, json.dumps(archived, ensure_ascii=False, indent=2))
            insights = insights[-200:]
        
        self.vault.write(path, json.dumps(insights, ensure_ascii=False, indent=2))
        self._insights_cache = insights

    def _load_all_insights(self) -> list[dict]:
        """Load all memories from the vault."""
        if self._insights_cache is not None:
            return self._insights_cache
        
        content = self.vault.read("system/memory-index.json")
        if content:
            try:
                self._insights_cache = json.loads(content)
                return self._insights_cache
            except json.JSONDecodeError:
                pass
        
        self._insights_cache = []
        return self._insights_cache

    def _load_archive(self) -> list[dict]:
        content = self.vault.read("system/memory-archive.json")
        if content:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass
        return []

    def _write_daily_summary(self, session_data, insights, now):
        """Write a daily learning summary to the journal."""
        date_str = now.strftime("%Y-%m-%d")
        path = f"journal/{date_str}.md"
        
        subject = session_data.get("subject_name", "")
        chapter = session_data.get("chapter_name", "")
        questions = session_data.get("questions", [])
        correct = sum(1 for q in questions if q.get("is_correct"))
        total = len(questions)
        
        entry = (
            f"\n### {now.strftime('%H:%M')} · {subject} - {chapter}\n"
            f"- 练习: {correct}/{total} 正确\n"
        )
        
        if insights:
            entry += "- 发现:\n"
            for ins in insights[:3]:
                entry += f"  - {ins['summary']}\n"
        
        content = self.vault.read(path) or f"# {date_str} 学习日志\n"
        self.vault.write(path, content + entry)


# ═══ Backward-compatible module-level functions ═══
# These call the MemoryManager internally

_manager_cache: dict[int, MemoryManager] = {}

def _get_manager(vault: VaultManager) -> MemoryManager:
    user_id = vault.user_id
    if user_id not in _manager_cache:
        _manager_cache[user_id] = MemoryManager(vault)
    return _manager_cache[user_id]


def record_practice_session(vault: VaultManager, session_data: dict):
    """Active-learning wrapper: extract insights from practice."""
    mgr = _get_manager(vault)
    return mgr.learn_from_practice(session_data)


def learn_from_chat(vault: VaultManager, user_message: str, agent_response: str, context: dict = None):
    """Extract insights from chat interactions."""
    mgr = _get_manager(vault)
    return mgr.learn_from_chat(user_message, agent_response, context)


def learn_from_reflect(vault: VaultManager, reflection_data: dict):
    """Learn from reflection sessions."""
    mgr = _get_manager(vault)
    return mgr.learn_from_reflect(reflection_data)


def get_relevant_memories(vault: VaultManager, subject: str = None, chapter: str = None, 
                          concept: str = None, limit: int = 10) -> list[dict]:
    """Get relevant memories for context building."""
    mgr = _get_manager(vault)
    return mgr.get_relevant_memories(subject, chapter, concept, limit)


def get_weaknesses(vault: VaultManager, subject: str = None) -> list[dict]:
    mgr = _get_manager(vault)
    return mgr.get_weaknesses(subject)


def update_mastery(vault: VaultManager, subject_name: str, chapter_name: str, total: int, correct: int):
    """Legacy compatibility wrapper."""
    mgr = _get_manager(vault)
    session_data = {
        "subject_name": subject_name,
        "chapter_name": chapter_name,
        "score": correct,
        "max_score": total,
        "questions": [{"is_correct": True} for _ in range(correct)] + 
                      [{"is_correct": False} for _ in range(total - correct)],
    }
    mgr._update_mastery_tracking(session_data, datetime.now(timezone.utc))


def write_journal_entry(vault: VaultManager, summary: str):
    """Append a simple journal entry (legacy)."""
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    path = f"journal/{date_str}.md"
    content = vault.read(path) or f"# {date_str} 学习日志\n"
    entry = f"\n**{now.strftime('%H:%M')}** · {summary}\n"
    vault.write(path, content + entry)


def append_memory(vault: VaultManager, insight: str, weight: int = 3):
    """Legacy compatibility: write an insight through MemoryManager."""
    mgr = _get_manager(vault)
    mgr._write_insight({
        "type": InsightType.PATTERN,
        "weight": weight,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": insight,
        "source": "legacy",
    })
