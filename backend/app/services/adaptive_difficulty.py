"""Adaptive Difficulty Engine — adjusts question difficulty based on user performance.

Rules:
- Correct 3x in a row at same difficulty → level up (+1)
- Wrong 2x in a row → level down (-1)
- First attempt at a knowledge point → start at difficulty 2
- Max difficulty: 5, Min: 1
- Tracks per (user, knowledge_point) pair via vault file
"""

import json
from datetime import datetime, timezone
from app.services.vault_manager import VaultManager

DIFFICULTY_FILE = "practice/difficulty_state.json"


def _load_state(vault: VaultManager) -> dict:
    raw = vault.read(DIFFICULTY_FILE) or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _save_state(vault: VaultManager, state: dict):
    vault.write(DIFFICULTY_FILE, json.dumps(state, ensure_ascii=False, indent=2))


def get_difficulty(vault: VaultManager, chapter_name: str, question_type: str = "single_choice") -> int:
    """Get current difficulty for a chapter. New chapters inherit average from others."""
    state = _load_state(vault)
    key = f"{chapter_name}|{question_type}"
    entry = state.get(key)
    if entry:
        return entry["difficulty"]
    # New chapter: use average of existing chapters
    all_diffs = [v["difficulty"] for k, v in state.items() if k.endswith(f"|{question_type}")]
    return round(sum(all_diffs) / len(all_diffs)) if all_diffs else 2


def record_result(
    vault: VaultManager,
    chapter_name: str,
    question_type: str,
    is_correct: bool,
) -> dict:
    """Record a single answer result and return updated difficulty info."""
    state = _load_state(vault)
    key = f"{chapter_name}|{question_type}"
    entry = state.get(key, {
        "difficulty": 2, "correct_streak": 0, "wrong_streak": 0,
        "last_result": None, "total_correct": 0, "total_attempts": 0,
    })

    entry["total_attempts"] = entry.get("total_attempts", 0) + 1
    if is_correct:
        entry["total_correct"] = entry.get("total_correct", 0) + 1
        entry["correct_streak"] = entry.get("correct_streak", 0) + 1
        entry["wrong_streak"] = 0  # Reset wrong streak on correct
    else:
        entry["wrong_streak"] = entry.get("wrong_streak", 0) + 1
        entry["correct_streak"] = 0  # Reset correct streak on wrong

    entry["last_result"] = is_correct

    # Apply level changes based on independent streaks
    old_diff = entry["difficulty"]
    if entry["correct_streak"] >= 3 and entry["difficulty"] < 5:
        entry["difficulty"] += 1
        entry["correct_streak"] = 0  # Reset after level-up
    elif entry["wrong_streak"] >= 2 and entry["difficulty"] > 1:
        entry["difficulty"] -= 1
        entry["wrong_streak"] = 0  # Reset after level-down

    state[key] = entry
    _save_state(vault, state)

    return {
        "previous_difficulty": old_diff,
        "new_difficulty": entry["difficulty"],
        "changed": old_diff != entry["difficulty"],
        "direction": "up" if entry["difficulty"] > old_diff else "down" if entry["difficulty"] < old_diff else "same",
        "correct_streak": entry["correct_streak"],
        "wrong_streak": entry["wrong_streak"],
        "total_attempts": entry["total_attempts"],
        "accuracy": round(entry["total_correct"] / entry["total_attempts"] * 100) if entry["total_attempts"] > 0 else 0,
    }


def get_adaptive_prompt_hint(vault: VaultManager, chapter_name: str, question_type: str = "single_choice") -> str:
    """Generate a prompt hint telling the AI what difficulty to generate."""
    diff = get_difficulty(vault, chapter_name, question_type)
    hints = {
        1: "出最基础的题目，确保学生理解核心概念。用最简单的数字和场景。",
        2: "出中等偏易的题目，巩固基本理解。",
        3: "出中等难度的题目，考察理解和应用。",
        4: "出中等偏难的题目，需要综合运用多个知识点。",
        5: "出高难度题目，接近竞赛或考研水平。需要深度推理。",
    }
    return hints.get(diff, hints[2])


def get_all_difficulties(vault: VaultManager) -> dict:
    """Get difficulty state for all tracked items."""
    return _load_state(vault)
