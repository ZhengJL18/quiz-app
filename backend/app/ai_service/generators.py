"""High-level AI generators for lesson content, questions, and explanations."""

import json
from pathlib import Path
from typing import Any

import yaml

from app.ai_service.client import DeepSeekClient

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _load_prompt(name: str) -> dict[str, str]:
    """Load a YAML prompt file and return as {role: content}."""
    path = _PROMPTS_DIR / f"{name}.yaml"
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data


async def generate_lesson_content(
    chapter_name: str,
    subject_name: str,
    *,
    client: DeepSeekClient | None = None,
) -> str:
    """Generate ~500-word lesson content in Chinese Markdown."""
    client = client or DeepSeekClient()
    sys_prompt = _load_prompt("base")

    messages = [
        {"role": "system", "content": sys_prompt["system"]},
        {
            "role": "user",
            "content": (
                f"请为《{subject_name}》课程中的「{chapter_name}」章节编写一份约500字的学习材料。\n\n"
                f"要求：\n"
                f"1. 使用中文 Markdown 格式\n"
                f"2. 包含核心知识点、重点难点和简单示例\n"
                f"3. 语言通俗易懂，适合学生自学\n"
                f"4. 如有公式或代码，请正确标注"
            ),
        },
    ]

    return await client.generate(messages, temperature=0.7, max_tokens=3000)


async def generate_questions(
    subject_name: str,
    chapter_name: str,
    count: int,
    difficulty_range: tuple[int, int] = (1, 5),
    *,
    client: DeepSeekClient | None = None,
) -> list[dict[str, Any]]:
    """Generate *count* questions for a given chapter.

    Returns a list of dicts, each compatible with the Question model fields.
    """
    client = client or DeepSeekClient()
    q_prompt = _load_prompt("question_gen")

    min_d, max_d = difficulty_range
    user_msg = q_prompt["user"].format(
        subject_name=subject_name,
        chapter_name=chapter_name,
        count=count,
        difficulty_min=min_d,
        difficulty_max=max_d,
    )

    messages = [
        {"role": "system", "content": q_prompt["system"]},
        {"role": "user", "content": user_msg},
    ]

    raw = await client.generate(messages, temperature=0.8, max_tokens=4096)

    # Strip possible markdown fences
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()

    try:
        questions = json.loads(raw)
        if isinstance(questions, dict):
            questions = [questions]
    except json.JSONDecodeError:
        raise ValueError(f"Failed to parse generated questions JSON:\n{raw}")

    return questions


async def generate_explanation(
    question_text: str,
    user_answer: str,
    correct_answer: str,
    subject_name: str,
    *,
    client: DeepSeekClient | None = None,
) -> str:
    """Generate a step-by-step explanation in Chinese Markdown."""
    client = client or DeepSeekClient()
    exp_prompt = _load_prompt("explanation")

    user_msg = exp_prompt["user"].format(
        question_text=question_text,
        user_answer=user_answer,
        correct_answer=correct_answer,
        subject_name=subject_name,
    )

    messages = [
        {"role": "system", "content": exp_prompt["system"]},
        {"role": "user", "content": user_msg},
    ]

    return await client.generate(messages, temperature=0.5, max_tokens=2000)


async def generate_similar_question(
    question_text: str,
    question_type: str,
    subject_name: str,
    chapter_name: str,
    difficulty: int,
    *,
    client: DeepSeekClient | None = None,
) -> dict[str, Any]:
    """Generate one similar question as a dict."""
    client = client or DeepSeekClient()
    sim_prompt = _load_prompt("similar")

    user_msg = sim_prompt["user"].format(
        question_text=question_text,
        question_type=question_type,
        subject_name=subject_name,
        chapter_name=chapter_name,
        difficulty=difficulty,
    )

    messages = [
        {"role": "system", "content": sim_prompt["system"]},
        {"role": "user", "content": user_msg},
    ]

    raw = await client.generate(messages, temperature=0.7, max_tokens=2048)

    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError(f"Failed to parse similar question JSON:\n{raw}")

    return result
