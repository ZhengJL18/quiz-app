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
    prompt_style: str | None = None,
    client: DeepSeekClient | None = None,
    api_key: str | None = None,
) -> str:
    """Generate ~500-word lesson content in Chinese Markdown."""
    client = client or DeepSeekClient(api_key=api_key)
    sys_prompt = _load_prompt("base")
    style_hint = f"\n\n出题风格要求：{prompt_style}" if prompt_style else ""

    messages = [
        {"role": "system", "content": sys_prompt["system"]},
        {
            "role": "user",
            "content": (
                f"为《{subject_name}》的「{chapter_name}」写约500字讲义。\n"
                f"规则：所有公式用 $...$ 包裹。用 **加粗** 标概念，用 - 列表。不寒暄。"
            ),
        },
    ]
    if style_hint:
        messages[1]["content"] += style_hint

    return await client.generate(messages, temperature=0.7, max_tokens=3000)


async def generate_questions(
    subject_name: str,
    chapter_name: str,
    count: int,
    difficulty_range: tuple[int, int] = (1, 5),
    *,
    prompt_style: str | None = None,
    client: DeepSeekClient | None = None,
    api_key: str | None = None,
) -> list[dict[str, Any]]:
    """Generate *count* questions for a given chapter.

    Returns a list of dicts, each compatible with the Question model fields.
    """
    client = client or DeepSeekClient(api_key=api_key)
    q_prompt = _load_prompt("question_gen")

    min_d, max_d = difficulty_range
    user_msg = q_prompt["user"].format(
        subject_name=subject_name,
        chapter_name=chapter_name,
        count=count,
        difficulty_min=min_d,
        difficulty_max=max_d,
    )
    if prompt_style:
        user_msg += f"\n\n出题风格要求：{prompt_style}"

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


def _format_options(options) -> str:
    """Format options list into labeled text for explanation prompts."""
    if not options:
        return "(无选项)"
    if isinstance(options, list):
        letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        items = []
        for i, opt in enumerate(options):
            label = letters[i] if i < 26 else str(i)
            items.append(f"  {label}. {opt}")
        return '\n'.join(items)
    return str(options)


def _format_correct_answer(correct_answer: str, options) -> str:
    """Format correct answer with its option text if available."""
    if not options or not isinstance(options, list):
        return correct_answer
    try:
        idx = int(correct_answer)
        if 0 <= idx < len(options):
            letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            label = letters[idx] if idx < 26 else str(idx)
            return f"{label}. {options[idx]}"
    except (ValueError, IndexError):
        pass
    return correct_answer


async def generate_explanation(
    question_text: str,
    user_answer: str,
    correct_answer: str,
    subject_name: str,
    *,
    options: list | None = None,
    client: DeepSeekClient | None = None,
    api_key: str | None = None,
) -> str:
    """Generate a step-by-step explanation in Chinese Markdown."""
    client = client or DeepSeekClient(api_key=api_key)
    exp_prompt = _load_prompt("explanation")

    options_text = _format_options(options)
    correct_text = _format_correct_answer(correct_answer, options)

    user_msg = exp_prompt["user"].format(
        question_text=question_text,
        options_text=options_text,
        user_answer=user_answer,
        correct_answer_text=correct_text,
        subject_name=subject_name,
    )

    messages = [
        {"role": "system", "content": exp_prompt["system"]},
        {"role": "user", "content": user_msg},
    ]

    return await client.generate(messages, temperature=0.5, max_tokens=2000)


async def generate_explanation_stream(
    question_text: str,
    user_answer: str,
    correct_answer: str,
    subject_name: str,
    *,
    options: list | None = None,
    client: DeepSeekClient | None = None,
    api_key: str | None = None,
):
    """Stream a step-by-step explanation, yielding text chunks."""
    client = client or DeepSeekClient(api_key=api_key)
    exp_prompt = _load_prompt("explanation")

    options_text = _format_options(options)
    correct_text = _format_correct_answer(correct_answer, options)

    user_msg = exp_prompt["user"].format(
        question_text=question_text,
        options_text=options_text,
        user_answer=user_answer,
        correct_answer_text=correct_text,
        subject_name=subject_name,
    )

    messages = [
        {"role": "system", "content": exp_prompt["system"]},
        {"role": "user", "content": user_msg},
    ]

    async for chunk in client.generate_stream(messages, temperature=0.5, max_tokens=2000, model="deepseek-chat"):
        yield chunk


async def generate_similar_question(
    question_text: str,
    question_type: str,
    subject_name: str,
    chapter_name: str,
    difficulty: int,
    *,
    client: DeepSeekClient | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Generate one similar question as a dict."""
    client = client or DeepSeekClient(api_key=api_key)
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


async def generate_lesson_content_stream(
    chapter_name: str,
    subject_name: str,
    *,
    prompt_style: str | None = None,
    client: DeepSeekClient | None = None,
    api_key: str | None = None,
):
    """Stream lesson content chunks via SSE. Yields text fragments."""
    client = client or DeepSeekClient(api_key=api_key)
    sys_prompt = _load_prompt("base")

    style_hint = f"\n出题风格参考：{prompt_style}" if prompt_style else ""
    messages = [
        {"role": "system", "content": sys_prompt["system"]},
        {
            "role": "user",
            "content": (
                f"为《{subject_name}》的「{chapter_name}」写约500字讲义。\n"
                f"规则：所有公式用 $...$ 包裹。用 **加粗** 标概念，用 - 列表。不寒暄。"
                f"{style_hint}"
            ),
        },
    ]

    async for chunk in client.generate_stream(messages, temperature=0.7, max_tokens=3000):
        yield chunk
