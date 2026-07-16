"""Scoring engine for objective question types."""

import json
from app.db.models import Question


def _parse_content_json(question: Question) -> dict:
    """Parse content_json safely."""
    if isinstance(question.content_json, dict):
        return question.content_json
    return json.loads(question.content_json)


def _normalize(text: str) -> str:
    """Strip whitespace and lowercase for comparison."""
    return text.strip().lower()


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
        None — question type requires AI grading (short_answer, calculation, proof)
    """
    content = _parse_content_json(question)

    if question.question_type == "single_choice":
        correct = content.get("correct_answer", "")
        return _normalize(user_answer) == _normalize(str(correct))

    elif question.question_type == "multiple_choice":
        correct_answers = content.get("correct_answers", content.get("correct_answer", []))
        if isinstance(correct_answers, str):
            correct_answers = json.loads(correct_answers)
        if not isinstance(correct_answers, list):
            correct_answers = [correct_answers]
        correct_set = {_normalize(str(a)) for a in correct_answers}
        user_set = {_normalize(a) for a in _parse_user_answers(user_answer)}
        return user_set == correct_set

    elif question.question_type == "fill_blank":
        correct_answers = content.get("correct_answers", content.get("correct_answer", []))
        if isinstance(correct_answers, str):
            try:
                correct_answers = json.loads(correct_answers)
            except (json.JSONDecodeError, TypeError):
                correct_answers = [correct_answers]
        if not isinstance(correct_answers, list):
            correct_answers = [correct_answers]
        normalized_user = _normalize(user_answer)
        return any(_normalize(str(ans)) == normalized_user for ans in correct_answers)

    elif question.question_type in ("short_answer", "calculation", "proof"):
        # Subjective; needs AI grading
        return None

    # Unknown type — treat as subjective
    return None
