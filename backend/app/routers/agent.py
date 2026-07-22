"""Agent router — onboarding, reflect, vault management."""

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.engine import get_db
from app.db.models import User, PracticeSession, QuestionAttempt, Question, Subject, Chapter, WrongBook, SRSSchedule
from app.dependencies import get_current_user
from app.services.vault_manager import get_vault
from app.services.agent_context import build_agent_context
from app.services.memory_writer import (
    record_practice_session,
    update_mastery,
    write_journal_entry,
    append_memory,
)

router = APIRouter()


# ── Schemas ──

class OnboardRequest(BaseModel):
    subjects: list[str] = []       # ["高等数学", "线性代数"]
    goal: str = ""                 # "高数期末90分"
    learning_style: str = ""       # "喜欢先看例子再学原理"


class ReflectRequest(BaseModel):
    session_id: int


class VaultInfo(BaseModel):
    size_mb: float
    file_count: int
    within_quota: bool


# ── Onboarding ──

@router.post("/onboard")
def onboard(
    body: OnboardRequest,
    current_user: User = Depends(get_current_user),
):
    """3-step onboarding wizard. Creates the user's vault with initial data."""
    vault = get_vault(current_user.id)
    result = vault.onboard(
        subjects=body.subjects,
        goal=body.goal,
        learning_style=body.learning_style,
    )
    return {"ok": True, "created": result}


# ── Reflect (post-practice self-learning) ──

@router.post("/reflect")
async def reflect(
    body: ReflectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """After a practice session, AI-powered reflect and vault update."""
    session = db.query(PracticeSession).filter_by(
        id=body.session_id, user_id=current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    vault = get_vault(current_user.id)

    # Gather session data
    attempts = db.query(QuestionAttempt).filter_by(session_id=session.id).all()
    questions_data = []
    total_correct = 0
    total_graded = 0

    for att in attempts:
        q = db.query(Question).filter_by(id=att.question_id).first()
        content = {}
        if q:
            try:
                content = json.loads(q.content_json) if isinstance(q.content_json, str) else q.content_json
            except (json.JSONDecodeError, TypeError):
                pass

        if att.is_correct is not None:
            total_graded += 1
            if att.is_correct:
                total_correct += 1

        questions_data.append({
            "type": q.question_type if q else "unknown",
            "question_text": content.get("question_text", "")[:200],
            "user_answer": att.user_answer or "",
            "correct_answer": str(content.get("correct_answer", content.get("correct_answers", ""))),
            "is_correct": att.is_correct,
            "time_spent": att.time_spent_seconds or 0,
        })

    subj_name = ""
    ch_name = ""
    if session.subject_id:
        subj = db.query(Subject).filter_by(id=session.subject_id).first()
        subj_name = subj.name if subj else ""
    if session.chapter_id:
        ch = db.query(Chapter).filter_by(id=session.chapter_id).first()
        ch_name = ch.name if ch else ""

    session_data = {
        "session_id": session.id, "mode": session.mode,
        "subject_name": subj_name, "chapter_name": ch_name,
        "score": total_correct, "max_score": total_graded,
        "questions": questions_data,
    }

    # 1. Basic file recording
    record_practice_session(vault, session_data)
    if subj_name and ch_name and total_graded > 0:
        update_mastery(vault, subj_name, ch_name, total_graded, total_correct)

        # Adaptive difficulty tracking
        from app.services.adaptive_difficulty import record_result
        for q in questions_data:
            if q.get("is_correct") is not None:
                record_result(vault, ch_name, q.get("type", "single_choice"), q["is_correct"])

    # 2. AI-powered deep reflection
    pct = f"{int(total_correct / total_graded * 100)}%" if total_graded > 0 else "N/A"
    ai_analyzed = False
    task_id = f"reflect_{body.session_id}"
    _task_track(vault, task_id, "pending", "starting AI analysis")
    try:
        from app.ai_service.client import DeepSeekClient
        ai = DeepSeekClient(api_key=current_user.api_key)

        # Read previous state for trend comparison
        prev_mastery = vault.read(f"讲义/{subj_name}/mastery.md") if subj_name else ""
        prev_journal = "\n".join([vault.read(f"日志/{f.name}") or "" for f in sorted((vault.root/"journal").glob("*.md"))[-3:]])

        reflect_prompt = f"""你是学习分析专家。分析以下练习数据并输出JSON。

=== 本轮练习 ===
科目: {subj_name}, 章节: {ch_name}, 模式: {session.mode}
正确率: {total_correct}/{total_graded} ({pct})
题目详情: {json.dumps(questions_data, ensure_ascii=False)[:1500]}

=== 近期掌握度 ===
{prev_mastery[:1000]}

=== 近期日志 ===
{prev_journal[:500]}

输出JSON（不要其他文字）：
{{
  "error_pattern": "错误模式分析(50字以内,如'换元后忘回代'而非'计算粗心')",
  "trend": "趋势判断(上升/下降/持平, 50字)",
  "journal_entry": "今日学习日志(100字,自然语言,有温度,含数据)",
  "new_insight": "关于用户的新认知(50字,如无新发现则写'无')",
  "insight_weight": 3,
  "portrait_update": "更新用户画像: 强项、弱项、学习风格(50字, 如无变化写'无')"
}}"""

        resp = await ai.generate(
            [{"role": "user", "content": reflect_prompt}],
            temperature=0.5, max_tokens=600, model="deepseek-chat"
        )

        # Parse AI response
        ai_data = json.loads(resp.strip().lstrip("```json").rstrip("```"))
        error_pattern = ai_data.get("error_pattern", "")
        journal_text = ai_data.get("journal_entry", f"完成 {session.mode} · {subj_name} {ch_name} · {pct}")
        new_insight = ai_data.get("new_insight", "")
        insight_weight = ai_data.get("insight_weight", 3)

        # Write AI-generated journal
        write_journal_entry(vault, journal_text)

        # Write new memory insight
        if new_insight and new_insight != "无":
            append_memory(vault, new_insight, weight=insight_weight)

        # If consistent mistakes
        if total_graded >= 3 and total_correct / total_graded < 0.5:
            append_memory(vault, f"[{ch_name}] {error_pattern} · 正确率{pct}", weight=4)

        # Update user portrait
        portrait_update = ai_data.get("portrait_update", "")
        if portrait_update and portrait_update != "无":
            existing = vault.read("画像/context.md") or ""
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
            vault.write("画像/context.md", existing.rstrip() + f"\n\n**{timestamp}** {portrait_update}")

        ai_analyzed = True
        _task_track(vault, task_id, "completed", f"error_pattern={error_pattern[:50]}")

    except Exception as e:
        # Fallback: simple journal
        write_journal_entry(vault, f"完成 {session.mode} · {subj_name} {ch_name} · {pct}")
        _task_track(vault, task_id, "failed", str(e)[:200])
        import logging
        logging.getLogger("uvicorn.error").warning(f"Reflect AI analysis failed: {e}")

    return {
        "ok": True, "session_saved": True,
        "mastery_updated": bool(subj_name and ch_name and total_graded > 0),
        "ai_analyzed": ai_analyzed,
    }


# ── Daily Plan Generation ──

class DailyPlanRequest(BaseModel):
    pass  # No params needed; reads from vault


@router.post("/daily-plan")
async def generate_daily_plan(
    body: DailyPlanRequest = DailyPlanRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI generates today's learning plan based on vault data. Streams the result."""
    vault = get_vault(current_user.id)

    # Gather context
    profile_goals = vault.read("画像/goals.md") or ""
    profile_prefs = vault.read("画像/preferences.md") or ""
    profile_portrait = vault.read("画像/context.md") or ""
    memory = vault.read("系统/memory.md") or ""
    knowledge_index = vault.read("讲义/index.md") or ""

    # Get SRS due count
    now = datetime.now(timezone.utc)
    srs_due = db.query(func.count(SRSSchedule.id)).join(
        WrongBook, SRSSchedule.wrong_book_id == WrongBook.id
    ).filter(
        WrongBook.user_id == current_user.id,
        SRSSchedule.next_review_at <= now,
    ).scalar() if hasattr(db, 'query') else 0

    # Recent journal
    journal_entries = []
    journal_dir = vault.root / "日志"
    if journal_dir.exists():
        for f in sorted(journal_dir.glob("*.md"), reverse=True)[:3]:
            try:
                journal_entries.append(f.read_text(encoding="utf-8", errors="replace")[:300])
            except Exception:
                pass

    async def event_stream():
        try:
            from app.ai_service.client import DeepSeekClient
            ai = DeepSeekClient(api_key=current_user.api_key)

            prompt = f"""你是学习规划专家。根据学生数据生成今日学习建议(100-150字)。

=== 学生目标 ===
{profile_goals[:300]}

=== 学习偏好 ===
{profile_prefs[:200]}

=== 知识掌握 ===
{knowledge_index[:500]}

=== 用户画像 ===
{profile_portrait[:300]}

=== 长期记忆 ===
{memory[:500]}

=== 近期日志 ===
{chr(10).join(journal_entries)[:500]}

=== 数据 ===
今日待复习错题: {srs_due} 题

要求：
1. 一句话问候
2. 今天1-3个具体任务（各10-15分钟）
3. 用 Markdown：**加粗**标关键，1. 2. 3. 列任务
4. 轻松有温度，不超过100字"""

            full = ""
            async for chunk in ai.generate_stream(
                [{"role": "user", "content": prompt}],
                temperature=0.7, max_tokens=400, model="deepseek-chat"
            ):
                full += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                await asyncio.sleep(0.01)

            # Save to today's journal
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            plan_path = f"日志/{date_str}.md"
            existing = vault.read(plan_path) or f"---\ndate: {date_str}\n---\n\n# 今日计划\n\n"
            vault.write(plan_path, existing + f"\n\n**AI 今日建议**: {full}\n")

            yield f"data: {json.dumps({'done': True, 'plan': full})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Vault Info ──

@router.get("/vault", response_model=VaultInfo)
def vault_info(current_user: User = Depends(get_current_user)):
    """Get vault storage info."""
    vault = get_vault(current_user.id)
    files = vault.list_files()
    return VaultInfo(
        size_mb=round(vault.size_mb(), 1),
        file_count=len(files),
        within_quota=vault.within_quota(),
    )


# ── Raw vault file read (for debugging / admin) ──

@router.get("/vault/file")
def read_vault_file(
    path: str = "",
    current_user: User = Depends(get_current_user),
):
    """Read a specific file from the user's vault."""
    vault = get_vault(current_user.id)
    content = vault.read(path)
    if content is None:
        raise HTTPException(status_code=404, detail="File not found")
    return {"path": path, "content": content}


# ── Agent Proactive Greeting ──

@router.get("/greeting")
async def agent_greeting(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Agent proactively greets the user. If they have no subjects, recommend starting."""
    from app.ai_service.client import DeepSeekClient

    vault = get_vault(current_user.id)
    goals = vault.read("画像/goals.md") or ""
    preferences = vault.read("画像/preferences.md") or ""

    # Check if user has subjects
    from app.db.models import Subject
    subject_count = db.query(func.count(Subject.id)).filter(
        Subject.user_id == current_user.id, Subject.is_active == True
    ).scalar()

    if subject_count == 0:
        # No subjects yet — fast template greeting (no AI call)
        async def event_stream():
            goal_text = goals[:100] or "未填写"
            greeting = (
                f"# 欢迎来到三一！🎓\n\n"
                f"你的目标：**{goal_text}**\n\n"
                f"---\n\n"
                f"看起来你还没有添加科目。你可以直接告诉我你想学什么，比如：\n\n"
                f"1. 「添加高等数学」\n"
                f"2. 「我要学线性代数」\n"
                f"3. 「帮我建C++的章节」\n\n"
                f"> 我会帮你自动创建科目、生成讲义和练习题。现在就开始？"
            )
            yield f"data: {json.dumps({'chunk': greeting})}\n\n"
            yield f"data: {json.dumps({'done': True, 'text': greeting, 'has_subjects': False})}\n\n"
    else:
        # Has subjects — fast greeting without AI call (avoid blocking)
        async def event_stream():
            # Read last journal entry for quick context
            journal_dir = vault.root / "日志"
            last_entry = ""
            if journal_dir.exists():
                recent = sorted(journal_dir.glob("*.md"), reverse=True)
                if recent:
                    last_entry = recent[0].read_text(encoding="utf-8", errors="replace")[:200]

            # Build quick greeting from vault data
            if last_entry:
                greeting = f"# 欢迎回来！\n\n上次学习记录：{last_entry[:80]}...\n\n---\n\n> 试试问我：**「今天有什么要复习的？」** 或 **「我哪一章最薄弱？」**"
            else:
                greeting = f"# 欢迎回来！\n\n你已添加 **{subject_count}** 个科目。\n\n---\n\n> 试试问我：**「今天有什么要复习的？」** 或 **「我哪一章最薄弱？」**"

            yield f"data: {json.dumps({'chunk': greeting})}\n\n"
            yield f"data: {json.dumps({'done': True, 'text': greeting, 'has_subjects': True})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Skill listing ──

@router.get("/skills")
def list_skills():
    """List available Agent skills with descriptions and example triggers."""
    from app.services.skill_router import SKILL_REGISTRY
    return [
        {
            "name": name,
            "label": config["name"],
            "description": config["description"],
            "example_trigger": config["triggers"][0] if config["triggers"] else "",
        }
        for name, config in SKILL_REGISTRY.items()
    ]


# ── Multi-model API key management ──

class ModelKeyUpdate(BaseModel):
    provider: str  # "kimi" | "doubao" | "qwen" | "tencent_asr_id" | "tencent_asr_key"
    api_key: str | None = None


@router.get("/model-keys")
def get_model_keys(current_user: User = Depends(get_current_user)):
    """Get which optional model keys the user has configured."""
    vault = get_vault(current_user.id)
    keys = {}
    for provider in ["kimi", "doubao", "qwen", "tencent_asr_id", "tencent_asr_key"]:
        stored = vault.read(f"画像/api_keys/{provider}.txt")
        keys[provider] = bool(stored and stored.strip())
    return keys


@router.put("/model-keys")
def set_model_key(
    body: ModelKeyUpdate,
    current_user: User = Depends(get_current_user),
):
    """Set or remove an optional model API key."""
    if body.provider not in ("kimi", "doubao", "qwen", "tencent_asr_id", "tencent_asr_key"):
        raise HTTPException(status_code=400, detail="Unsupported provider")
    vault = get_vault(current_user.id)
    if body.api_key:
        vault.write(f"画像/api_keys/{body.provider}.txt", body.api_key.strip())
    else:
        # Remove key
        path = vault.root / "profile" / "api_keys" / f"{body.provider}.txt"
        if path.exists():
            path.unlink()
    return {"ok": True, "provider": body.provider, "has_key": bool(body.api_key)}


# ── File upload + AI processing (raw file NOT stored) ──

from fastapi import UploadFile, File, Form

# Semaphore: prevent concurrent RAG indexing from overwhelming the server
_upload_semaphore = asyncio.Semaphore(2)


def _task_track(vault, task_id: str, status: str, detail: str = ""):
    """Record task status in _tasks.json for observability."""
    import json as _json
    from datetime import datetime as _dt
    path = vault.root / "_tasks.json"
    tasks = {}
    if path.exists():
        try:
            tasks = _json.loads(path.read_text(encoding="utf-8"))
        except _json.JSONDecodeError:
            pass
    tasks[task_id] = {"status": status, "detail": detail, "time": _dt.now(timezone.utc).isoformat()}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json.dumps(tasks, ensure_ascii=False, indent=2))


@router.post("/process-file")
async def process_chat_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Lightweight file processing for chat — returns extracted text without storing."""
    from app.services.model_router import ModelRouter

    file_data = await file.read()
    if len(file_data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件超过10MB限制")

    ext = (file.filename or "").lower().rsplit(".", 1)[-1] if "." in (file.filename or "") else ""
    ALLOWED = ("pdf", "png", "jpg", "jpeg", "gif", "webp", "bmp", "txt", "md", "py", "cpp", "c", "java", "js", "ts", "html", "css", "json", "xml", "yaml", "yml", "mp3", "wav", "m4a", "ogg", "webm", "flac", "aac")
    if ext not in ALLOWED:
        raise HTTPException(status_code=400, detail=f"不支持 .{ext}")

    # Strip metadata + compress images (EXIF, profiles, thumbnails etc.)
    if ext in ("png", "jpg", "jpeg", "gif", "webp", "bmp"):
        try:
            from PIL import Image
            import io as pil_io
            img = Image.open(pil_io.BytesIO(file_data))
            orig_size = len(file_data)

            # Strip all metadata: EXIF, ICC profile, comments, thumbnails
            data = list(img.getdata()) if img.mode != 'P' else None
            # Create clean image with only pixel data
            clean = Image.new(img.mode, img.size) if img.mode != 'P' else Image.new('RGB', img.size)
            if data:
                clean.putdata(data)
            else:
                clean = img.convert('RGB')

            # Resize if > 2000px
            w, h = clean.size
            if w > 2000 or h > 2000:
                ratio = 2000 / max(w, h)
                clean = clean.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

            # Save without metadata
            out = pil_io.BytesIO()
            fmt = 'JPEG' if ext in ('jpg', 'jpeg') else 'PNG'
            if fmt == 'JPEG':
                clean.save(out, format='JPEG', quality=85, optimize=True, exif=b'', icc_profile=None)
            else:
                clean.save(out, format='PNG', optimize=True, exif=b'', icc_profile=None)

            compressed = out.getvalue()
            if len(compressed) < orig_size:
                file_data = compressed
        except Exception:
            pass  # If Pillow fails, use original

    # For audio files — use Tencent Cloud ASR (if configured)
    if ext in ("mp3", "wav", "m4a", "ogg", "webm", "flac", "aac"):
        vault = get_vault(current_user.id)
        tencent_id = vault.read("画像/api_keys/tencent_asr_id.txt")
        tencent_key = vault.read("画像/api_keys/tencent_asr_key.txt")
        if tencent_id and tencent_id.strip() and tencent_key and tencent_key.strip():
            from app.services.tencent_asr import TencentASR
            try:
                asr = TencentASR(secret_id=tencent_id.strip(), secret_key=tencent_key.strip())
                text = await asr.recognize(file_data, voice_format=ext)
                return {"text": f"【音频转写：{file.filename}】\n\n{text}"}
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"语音识别失败：{str(e)[:200]}")
        return {
            "text": (
                f"【音频：{file.filename}】\n\n"
                f"> ⚠️ 语音转文字需要配置腾讯云 ASR。\n"
                f"> 请在 设置 → AI 模型密钥 中配置 Tencent ASR SecretId 和 SecretKey。"
            )
        }

    # For plain text files, just read directly
    if ext in ("txt", "md", "py", "cpp", "c", "java", "js", "ts", "html", "css", "json", "xml", "yaml", "yml"):
        try:
            text = file_data.decode("utf-8")
        except UnicodeDecodeError:
            text = file_data.decode("gbk", errors="replace")
        return {"text": f"【文件：{file.filename}】\n\n```{ext}\n{text[:5000]}\n```"}

    # For images/PDFs — need vision model (Kimi/Doubao/Qwen)
    api_keys = {"deepseek": current_user.api_key}
    vault = get_vault(current_user.id)
    vision_available = []
    for provider in ["kimi", "doubao", "qwen"]:
        stored_key = vault.read(f"画像/api_keys/{provider}.txt")
        if stored_key and stored_key.strip():
            api_keys[provider] = stored_key.strip()
            vision_available.append(provider)

    if not vision_available:
        names = {"kimi": "Kimi", "doubao": "豆包", "qwen": "千问"}
        return {
            "text": (
                f"【文件：{file.filename}】\n\n"
                f"> ⚠️ 图片/PDF 需要视觉模型支持。你当前只配了 DeepSeek（不支持视觉）。\n"
                f"> 请在 设置 → AI 模型密钥 中配置 Kimi / 豆包 / 千问 的 API Key，\n"
                f"> 然后在 AI 对话框切换到对应模型后再上传文件。"
            )
        }

    router = ModelRouter(api_keys)
    try:
        markdown = await router.process_media_to_markdown(
            file_data=file_data, file_name=file.filename or "upload",
            instruction="请提取此文件中的文字内容。如有公式用 $...$ 包裹。输出 Markdown。",
        )
        return {"text": f"【文件：{file.filename}】\n\n{markdown[:5000]}"}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"处理失败：{str(e)[:200]}")


@router.post("/upload-material")
async def upload_material(
    file: UploadFile = File(...),
    instruction: str = Form("请提取此文件中的全部文字内容，包括公式和表格。输出为Markdown格式。"),
    current_user: User = Depends(get_current_user),
):
    """Upload a PDF/image, process through multi-modal AI, store only Markdown in vault.

    The original file is NOT persisted on the server.
    If no multi-modal key is configured, falls back to PyMuPDF text extraction.
    """
    from app.services.model_router import ModelRouter

    # Read file into memory
    file_data = await file.read()
    if len(file_data) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件超过50MB限制")

    # File type whitelist
    ext = (file.filename or "").lower().rsplit(".", 1)[-1] if "." in (file.filename or "") else ""
    if ext not in ("pdf", "png", "jpg", "jpeg", "gif", "webp", "bmp"):
        raise HTTPException(status_code=400, detail=f"不支持的文件类型 .{ext}，仅支持 PDF/PNG/JPG/GIF/WEBP")

    # Quota check
    if not vault.within_quota():
        raise HTTPException(status_code=413, detail=f"存储空间不足（上限 1GB），当前已用 {vault.size_mb():.0f}MB")

    # Build model router with user's API keys
    api_keys = {"deepseek": current_user.api_key}
    # Check for additional model keys in user settings (stored in vault)
    vault = get_vault(current_user.id)
    for provider in ["kimi", "doubao", "qwen"]:
        stored_key = vault.read(f"画像/api_keys/{provider}.txt")
        if stored_key:
            api_keys[provider] = stored_key.strip()

    router = ModelRouter(api_keys)

    try:
        markdown = await router.process_media_to_markdown(
            file_data=file_data,
            file_name=file.filename or "upload",
            instruction=instruction,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI 处理失败：{str(e)[:200]}")

    # Store the Markdown result in the vault
    safe_name = (file.filename or "upload").rsplit(".", 1)[0]
    safe_name = "".join(c for c in safe_name if c.isalnum() or c in "_- ()[]（）")
    vault_path = f"素材/{safe_name}.md"

    # Append if exists, otherwise create
    existing = vault.read(vault_path)
    if existing:
        vault.write(vault_path, existing + "\n\n---\n\n" + markdown)
    else:
        vault.write(vault_path, markdown)

    # Update materials index
    index = vault.read("素材/index.md") or "# 资料目录\n\n"
    if safe_name not in index:
        index += f"- [{safe_name}]({safe_name}.md) — {len(markdown)} 字\n"
        vault.write("素材/index.md", index)

    # Auto-index into Chroma for RAG search (fire-and-forget)
    asyncio.create_task(_index_material_bg(current_user.id, markdown, vault_path, current_user.api_key))

    return {
        "ok": True,
        "path": vault_path,
        "size": len(markdown),
        "preview": markdown[:200],
    }


async def _index_material_bg(user_id: int, content: str, source: str, api_key: str):
    """Background: index uploaded material into Chroma (rate-limited + tracked)."""
    vault = get_vault(user_id)
    task_id = f"rag_index_{source}"
    _task_track(vault, task_id, "pending", "waiting for slot")
    async with _upload_semaphore:
        _task_track(vault, task_id, "processing", "embedding chunks...")
        try:
            from app.services.rag_engine import index_document
            chunks = await index_document(user_id, content, source, api_key)
            _task_track(vault, task_id, "completed", f"indexed {chunks} chunks")
            import logging
            logging.getLogger("uvicorn.error").info(f"RAG: indexed {chunks} chunks for user {user_id} from {source}")
        except Exception as e:
            _task_track(vault, task_id, "failed", str(e)[:200])
            import logging
            logging.getLogger("uvicorn.error").warning(f"RAG index failed: {e}")


# ── RAG Search ──

class SearchRequest(BaseModel):
    query: str
    top_k: int = 3


@router.post("/search-materials")
async def search_materials(
    body: SearchRequest,
    current_user: User = Depends(get_current_user),
):
    """Semantic search over user's indexed materials."""
    from app.services.rag_engine import search_materials as rag_search
    results = await rag_search(current_user.id, body.query, current_user.api_key, body.top_k)
    return {"results": results}


# ── Adaptive Difficulty ──

@router.get("/difficulty")
def get_difficulty_state(current_user: User = Depends(get_current_user)):
    """Get adaptive difficulty state for all tracked chapters."""
    from app.services.adaptive_difficulty import get_all_difficulties
    vault = get_vault(current_user.id)
    return {"state": get_all_difficulties(vault)}


# ── Class Notes Generation ──

@router.post("/generate-class-notes")
async def generate_class_notes(
    transcript: str = Form(""),
    notes: str = Form(""),
    course_name: str = Form(""),
    images: list[UploadFile] = File(default=[]),
    current_user: User = Depends(get_current_user),
):
    """Generate structured class notes from transcript, hand-written notes, and images.

    Accepts multipart form data with:
    - transcript: audio transcription text
    - notes: hand-written / manual notes text
    - images: up to 10 image files (PNG/JPG/WEBP/GIF/BMP)
    - course_name: name of the course

    Returns streaming SSE markdown with structured notes.
    """
    if len(images) > 10:
        raise HTTPException(status_code=400, detail="图片数量超过上限（最多10张）")

    # Read and compress images
    processed_images: list[tuple[bytes, str]] = []
    for img_file in images:
        if not img_file.filename:
            continue
        ext = (img_file.filename or "").lower().rsplit(".", 1)[-1]
        if ext not in ("png", "jpg", "jpeg", "gif", "webp", "bmp"):
            continue
        try:
            img_data = await img_file.read()
            from PIL import Image
            import io as pil_io
            img = Image.open(pil_io.BytesIO(img_data))

            # Strip metadata
            clean = Image.new("RGB", img.size) if img.mode == "P" else Image.new(img.mode, img.size)
            data = list(img.getdata()) if img.mode != "P" else list(img.convert("RGB").getdata())
            clean.putdata(data)

            # Resize if > 2000px
            w, h = clean.size
            if w > 2000 or h > 2000:
                ratio = 2000 / max(w, h)
                clean = clean.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

            out = pil_io.BytesIO()
            clean.save(out, format="PNG", optimize=True)
            compressed = out.getvalue()
            if len(compressed) < len(img_data):
                processed_images.append((compressed, img_file.filename))
            else:
                processed_images.append((img_data, img_file.filename))
        except Exception:
            pass  # Skip problematic images

    # Build prompt
    prompt_parts = ["你是课堂笔记助手。根据录音转写、手写笔记和课堂图片，生成一份结构化的课堂笔记。用 Markdown + LaTeX。"]
    if course_name:
        prompt_parts.append(f"\n## 课程信息\n课程名称：{course_name}")
    if transcript:
        prompt_parts.append(f"\n## 录音转写\n{transcript}")
    if notes:
        prompt_parts.append(f"\n## 手写笔记\n{notes}")
    if processed_images:
        prompt_parts.append(f"\n## 课堂图片（{len(processed_images)}张）\n请结合图片中的板书、讲义或图示内容完善笔记。")
    prompt_parts.append("\n---\n\n请生成完整的课堂笔记（结构清晰、提取核心概念、公式用 $$ 包裹）：")
    full_prompt = "\n".join(prompt_parts)

    vault = get_vault(current_user.id)

    async def event_stream():
        try:
            # Check for vision model availability
            api_keys = {"deepseek": current_user.api_key}
            vision_providers = []
            for provider in ["kimi", "doubao", "qwen"]:
                stored_key = vault.read(f"画像/api_keys/{provider}.txt")
                if stored_key and stored_key.strip():
                    api_keys[provider] = stored_key.strip()
                    vision_providers.append(provider)

            has_images = len(processed_images) > 0

            if has_images and not vision_providers:
                msg = '> 图片分析需要视觉模型（Kimi/豆包/千问），请在设置中配置 API Key。\n\n'
                yield f"data: {json.dumps({'chunk': msg})}\n\n"
                # Fall through to text-only generation

            if has_images and vision_providers:
                # Stream from vision model
                from app.services.model_router import ModelRouter
                router = ModelRouter(api_keys)
                async for chunk in router.stream_vision(full_prompt, processed_images):
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                    await asyncio.sleep(0.01)
            else:
                # Text-only: use DeepSeek streaming
                from app.ai_service.client import DeepSeekClient
                ai = DeepSeekClient(api_key=current_user.api_key)
                async for chunk in ai.generate_stream(
                    [{"role": "user", "content": full_prompt}],
                    temperature=0.6, max_tokens=4096, model="deepseek-chat",
                ):
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                    await asyncio.sleep(0.01)

            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            import traceback
            error_detail = f"{type(e).__name__}: {e}"
            logging = __import__("logging").getLogger("uvicorn.error")
            logging.warning(f"Generate class notes failed: {error_detail}\n{traceback.format_exc()}")
            yield f"data: {json.dumps({'error': str(e)[:300]})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
