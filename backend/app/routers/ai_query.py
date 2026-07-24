"""Structured AI query endpoint — versioned prompts, JSON output, streaming."""
import json, asyncio, re
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from app.db.models import User
from app.dependencies import get_current_user

router = APIRouter()


class AIQueryRequest(BaseModel):
    selected: str
    context_before: str = ""
    context_after: str = ""
    page_type: str = "general"
    version: str = "v3"  # v1, v2, v3


# ── Prompt builders ──

def build_v1_prompt(selected: str) -> str:
    return f"""你是高数老师。把输入整理为标准数学问题，给出解题步骤。

输出 JSON（不要其他文字）：
{{
  "understanding": "问题理解（一句话）",
  "latex": "LaTeX公式（必须$...$包裹）",
  "steps": ["步骤1", "步骤2"],
  "key_idea": "核心思路",
  "summary": "一句话总结"
}}

输入：{selected}"""


def build_v2_prompt(selected: str, context_before: str, context_after: str, page_type: str) -> str:
    ctx = ""
    if context_before: ctx += f"上文：{context_before[:200]}\n"
    if context_after: ctx += f"下文：{context_after[:200]}\n"
    return f"""你是高数老师。根据上下文补全问题并讲解。

输出 JSON：
{{
  "understanding": "补全后的问题",
  "latex": "公式（$...$包裹）",
  "steps": ["步骤"],
  "key_idea": "核心思路",
  "mistakes": "常见错误",
  "summary": "总结"
}}

选中：{selected}
{ctx}类型：{page_type}"""


def build_v3_prompt(selected: str, context_before: str, context_after: str, page_type: str) -> str:
    ctx = f"类型：{page_type}"
    if context_before: ctx += f"\n上文：{context_before[:300]}"
    if context_after: ctx += f"\n下文：{context_after[:300]}"
    return f"""你是高数老师。目标是让学生"看一眼就懂"。

输出 JSON：
{{
  "topic": "知识点",
  "what_is_this": "一句话解释",
  "formula": "公式（$...$包裹）",
  "steps": ["步骤1", "步骤2"],
  "intuition": "直观理解（大白话）",
  "common_traps": ["易错1"],
  "summary": "一句话核心"
}}

输入：{selected}
{ctx}"""


PROMPT_BUILDERS = {"v1": build_v1_prompt, "v2": build_v2_prompt, "v3": build_v3_prompt}


@router.post("/query")
async def ai_query(
    body: AIQueryRequest,
    current_user: User = Depends(get_current_user),
):
    """Core AI query endpoint — structured math explanation with streaming."""
    builder = PROMPT_BUILDERS.get(body.version, build_v3_prompt)
    prompt = builder(body.selected, body.context_before, body.context_after, body.page_type)

    async def event_stream():
        try:
            from app.ai_service.client import DeepSeekClient
            ai = DeepSeekClient(api_key=current_user.api_key)

            full = ""
            async for chunk in ai.generate_stream(
                [{"role": "user", "content": prompt}],
                temperature=0.3, max_tokens=1500, model="deepseek-chat"
            ):
                full += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                await asyncio.sleep(0.01)

            # Try to parse JSON from response
            clean = full.strip()
            # Strip markdown code fences
            clean = re.sub(r'^```(?:json)?\s*', '', clean)
            clean = re.sub(r'\s*```$', '', clean)
            try:
                parsed = json.loads(clean)
                yield f"data: {json.dumps({'done': True, 'structured': parsed})}\n\n"
            except json.JSONDecodeError:
                # Fallback: wrap raw text
                yield f"data: {json.dumps({'done': True, 'structured': {'raw': full, 'summary': full[:200]}})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)[:200]})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
