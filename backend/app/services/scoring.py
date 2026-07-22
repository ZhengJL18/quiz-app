"""Scoring engine for objective question types."""

import json
import re
from app.db.models import Question


def _parse_content_json(question: Question) -> dict:
    """Parse content_json safely."""
    if isinstance(question.content_json, dict):
        return question.content_json
    return json.loads(question.content_json)


def _normalize(text: str) -> str:
    """Strip whitespace and lowercase for comparison."""
    return text.strip().lower()


def _choice_to_index(value: str) -> str:
    """Normalize choice answers: A→0, B→1, etc. Handles both letter and numeric formats.

    Also handles mixed input like 'A' → '0', '0' → '0'.
    """
    v = value.strip().upper()
    # Letter → index: A→0, B→1, C→2, D→3, E→4, F→5, G→6, H→7
    if re.match(r'^[A-H]$', v):
        return str(ord(v) - ord('A'))
    # Already numeric: return as-is
    return v


def _parse_user_answers(user_answer: str) -> list[str]:
    """Parse user answer into a list of individual answers."""
    user_answer = user_answer.strip()
    if not user_answer:
        return []
    # Try JSON first
    if user_answer.startswith("[") or user_answer.startswith('"'):
        try:
            parsed = json.loads(user_answer)
            if isinstance(parsed, list):
                return [str(a).strip() for a in parsed]
            return [str(parsed).strip()]
        except (json.JSONDecodeError, TypeError):
            pass
    # Fall back to comma-separated
    return [a.strip() for a in user_answer.split(",") if a.strip()]


def grade_answer(question: Question, user_answer: str) -> bool | None:
    """Grade an objective question.

    Returns:
        bool — correct or incorrect
        None — question type requires self-grading (fill_blank, short_answer, calculation, proof)
    """
    content = _parse_content_json(question)

    if question.question_type == "single_choice":
        correct = _choice_to_index(str(content.get("correct_answer", "")))
        user = _choice_to_index(user_answer)
        return user == correct

    elif question.question_type == "multiple_choice":
        correct_answers = content.get("correct_answers", content.get("correct_answer", []))
        if isinstance(correct_answers, str):
            try:
                correct_answers = json.loads(correct_answers)
            except (json.JSONDecodeError, TypeError):
                correct_answers = [correct_answers]
        if not isinstance(correct_answers, list):
            correct_answers = [correct_answers]
        correct_set = {_choice_to_index(str(a)) for a in correct_answers}
        user_set = {_choice_to_index(a) for a in _parse_user_answers(user_answer)}
        return user_set == correct_set

    elif question.question_type == "fill_blank":
        # Subjective — let user self-judge after seeing AI explanation
        return None

    elif question.question_type in ("short_answer", "calculation", "proof"):
        # Subjective — needs user self-judge
        return None

    # Unknown type — treat as subjective
    return None
