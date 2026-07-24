"""AI Assistant router — chat with tool execution & streaming."""
import json, re, asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional

from app.ai_service.client import DeepSeekClient
from app.ai_service.generators import (
    generate_questions, generate_lesson_content, generate_similar_question,
    generate_lesson_content_stream,
)
from app.db.engine import get_db
from app.db.models import User, Subject, Chapter, Question, WrongBook, PracticeSession, ChapterMastery, VocabCard, SRSSchedule
from app.dependencies import get_current_user

router = APIRouter()

# ── Schemas ──
class ChatRequest(BaseModel):
    messages: list[dict] = []
    page_context: str = ""
    model: str = "deepseek"  # deepseek, kimi, doubao, qwen
    model_config = {"extra": "allow"}

class ChatResponse(BaseModel):
    reply: str
    actions: list[str] = []
    context: str = ""

class FollowUpRequest(BaseModel):
    question_id: int
    question_text: str = ""
    explanation: str = ""
    user_answer: str = ""
    correct_answer: str = ""
    follow_up: str

# ── Tool helpers ──

SYSTEM_PROMPT_BASE = (
    "你是三一学习平台的 AI 助教。用中文 Markdown 回复，简洁直接。\n\n"
    "【格式铁律】\n"
    "1. 所有数学公式必须 $...$ 包裹，块级用 $$...$$。绝对禁止裸写公式。\n"
    "2. 用 **加粗** 标重点，用 - 列表组织内容。\n"
    "3. 不寒暄，不写\"同学你好\"。\n\n"
    "【讲解格式】（可选用于详细解答）\n"
    "📌 **理解**：一句话 | 📐 **公式**：$...$ | 🧠 **步骤**：1. 2. 3. | 💡 **思路**：关键直觉 | ⚠️ **易错**：常见错误\n\n"
    "【操作指令】需要执行操作时插入 ACTION 标签：\n"
    "- [ACTION:BATCH_ADD_CHAPTERS]{\"subject\":\"学科\",\"chapters\":[{\"name\":\"章\",\"level\":1},{\"name\":\"节\",\"level\":2}]}[/ACTION]\n"
    "- [ACTION:ADD_SUBJECT]{\"name\":\"学科\"}[/ACTION]\n"
    "- [ACTION:GENERATE_QUESTIONS]{\"subject\":\"学科\",\"chapter\":\"章\",\"count\":5}[/ACTION]\n"
    "- [ACTION:GENERATE_LESSON]{\"subject\":\"学科\",\"chapter\":\"章\"}[/ACTION]\n"
    "- [ACTION:SEARCH_MATERIALS]{\"query\":\"关键词\"}[/ACTION]\n"
    "- [ACTION:READ_MATERIAL]{\"filename\":\"文件.md\"}[/ACTION]\n"
    "- [ACTION:LIST_CHAPTERS]{\"subject\":\"学科\"}[/ACTION] / [ACTION:LIST_SUBJECTS]{}[/ACTION]\n"
    "- [ACTION:DASHBOARD]{}[/ACTION] / [ACTION:ANALYZE_MASTERY]{\"subject\":\"学科\"}[/ACTION]\n"
    "- [ACTION:WRONG_SUMMARY]{}[/ACTION] / [ACTION:GENERATE_SIMILAR]{\"subject\":\"学科\",\"chapter\":\"章\",\"reference_question\":\"题\"}[/ACTION]\n"
    "- [ACTION:DELETE_SUBJECT]{\"name\":\"学科\"}[/ACTION] / [ACTION:RENAME_SUBJECT]{\"old_name\":\"旧\",\"new_name\":\"新\"}[/ACTION]\n"
    "最多 5 轮操作。不需要操作时直接回复。\n\n"
)


def _build_context(user: User, db: Session) -> str:
    from sqlalchemy import and_

    subjects = db.query(Subject).filter(Subject.user_id == user.id, Subject.is_active == True).all()
    if not subjects:
        return "User has no subjects yet."

    ctx = f"User: {user.username}\n"
    weak_chapters = []

    for s in subjects:
        chapters = db.query(func.count(Chapter.id)).filter(Chapter.subject_id == s.id).scalar()
        questions = db.query(func.count(Question.id)).filter(Question.subject_id == s.id).scalar()
        ctx += f"- {s.name}: {chapters} chapters, {questions} questions"
        if s.prompt_style:
            ctx += f", style: {s.prompt_style}"

        # Append mastery data for leaf chapters
        leaf_chs = db.query(Chapter).filter(
            Chapter.subject_id == s.id, Chapter.is_leaf == True
        ).all()
        low = []
        for ch in leaf_chs:
            m = db.query(ChapterMastery).filter(
                and_(ChapterMastery.chapter_id == ch.id, ChapterMastery.user_id == user.id)
            ).first()
            if m and m.mastery_score is not None and m.mastery_score < 0.6:
                low.append(f"{ch.name}({int(m.mastery_score*100)}%)")
        if low:
            ctx += f"\n  Weak: {', '.join(low[:5])}"
            weak_chapters.extend(low)
        ctx += "\n"

    wrong_count = db.query(func.count(WrongBook.id)).filter(WrongBook.user_id == user.id).scalar()
    total_sessions = db.query(func.count(PracticeSession.id)).filter(PracticeSession.user_id == user.id).scalar()
    ctx += f"\nTotal practice: {total_sessions}, wrong answers: {wrong_count}\n"

    # SRS due count
    now = datetime.now(timezone.utc)
    srs_due = db.query(func.count(SRSSchedule.id)).join(
        WrongBook, SRSSchedule.wrong_book_id == WrongBook.id
    ).filter(
        WrongBook.user_id == user.id,
        SRSSchedule.next_review_at <= now
    ).scalar()
    ctx += f"待复习错题: {srs_due}\n"

    if weak_chapters:
        ctx += f"\nRecommendation: Focus on {'; '.join(weak_chapters[:3])}\n"

    return ctx


# ── Model client factory ──

MODEL_REGISTRY = {
    "deepseek": {"name": "DeepSeek", "base_url": "https://api.deepseek.com", "chat_model": "deepseek-chat"},
    "kimi": {"name": "Kimi", "base_url": "https://api.moonshot.cn/v1", "chat_model": "moonshot-v1-8k"},
    "doubao": {"name": "豆包", "base_url": "https://ark.cn-beijing.volces.com/api/v3", "chat_model": "doubao-pro-32k"},
    "qwen": {"name": "千问", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "chat_model": "qwen-plus"},
}

def _get_model_client(user: User, model: str = "deepseek") -> DeepSeekClient:
    """Get AI client for the specified model. Falls back to DeepSeek if key unavailable."""
    cfg = MODEL_REGISTRY.get(model, MODEL_REGISTRY["deepseek"])
    if model == "deepseek":
        return DeepSeekClient(api_key=user.api_key)
    # Check if user has an API key for this model in vault
    from app.services.vault_manager import get_vault
    vault = get_vault(user.id)
    stored_key = vault.read(f"画像/api_keys/{model}.txt")
    if stored_key and stored_key.strip():
        return DeepSeekClient(api_key=stored_key.strip(), base_url=cfg["base_url"])
    # Fall back to DeepSeek
    return DeepSeekClient(api_key=user.api_key)


def _parse_actions(response: str) -> list[dict]:
    actions = []
    for m in re.finditer(r'\[ACTION:(\w+)\](.*?)\[/ACTION\]', response, re.DOTALL):
        try:
            payload = json.loads(m.group(2))
            actions.append({"type": m.group(1), "payload": payload})
        except json.JSONDecodeError:
            pass
    return actions


async def _execute_action(action: dict, user: User, db: Session, user_api_key: str | None = None) -> str:
    t = action["type"]
    p = action["payload"]

    if t == "ADD_SUBJECT":
        name = p.get("name", "")
        if not name: return "ERROR: subject name required"
        if db.query(Subject).filter(Subject.user_id == user.id, Subject.name == name).first():
            return f"Subject '{name}' already exists"
        subj = Subject(user_id=user.id, name=name, description=p.get("description", ""),
                       prompt_style=p.get("prompt_style", ""), order_index=99)
        db.add(subj); db.commit()
        return f"Created subject: {name}"

    if t == "UPDATE_PROMPT":
        subj_name = p.get("subject", "")
        style = p.get("prompt_style", "")
        subj = db.query(Subject).filter(Subject.user_id == user.id, Subject.name == subj_name).first()
        if not subj: return f"Subject '{subj_name}' not found"
        subj.prompt_style = style; db.commit()
        return f"Updated prompt style for '{subj_name}'"

    if t == "ADD_CHAPTER":
        subj_name = p.get("subject", "")
        ch_name = p.get("name", "")
        subj = db.query(Subject).filter(Subject.user_id == user.id, Subject.name == subj_name).first()
        if not subj: return f"Subject '{subj_name}' not found"
        max_order = db.query(func.max(Chapter.order_index)).filter(Chapter.subject_id == subj.id).scalar() or 0
        ch = Chapter(subject_id=subj.id, name=ch_name, level=p.get("level", 3),
                     order_index=max_order + 1, is_leaf=p.get("is_leaf", True))
        db.add(ch); db.flush()
        db.commit()
        # Auto-trigger BG fill for the new chapter
        asyncio.create_task(_assistant_bg_lesson(ch.id, ch.name, subj.name, subj.prompt_style, user_api_key))
        asyncio.create_task(_assistant_bg_questions(ch.id, subj.name, ch.name, 8, subj.prompt_style, user_api_key))
        return f"Created chapter '{ch_name}' under '{subj_name}' — lesson & questions generating in background"

    if t == "FILL_CHAPTER":
        subj_name = p.get("subject", "")
        ch_name = p.get("chapter", "")
        subj = db.query(Subject).filter(Subject.user_id == user.id, Subject.name == subj_name).first()
        if not subj: return f"Subject '{subj_name}' not found"
        ch = db.query(Chapter).filter(Chapter.subject_id == subj.id, Chapter.name == ch_name, Chapter.is_leaf == True).first()
        if not ch: return f"Leaf chapter '{ch_name}' not found in '{subj_name}'"
        asyncio.create_task(_assistant_bg_lesson(ch.id, ch.name, subj.name, subj.prompt_style, user_api_key))
        asyncio.create_task(_assistant_bg_questions(ch.id, subj.name, ch.name, 8, subj.prompt_style, user_api_key))
        return f"Started background fill for '{ch_name}': lesson content + 8 questions"

    if t == "BATCH_ADD_CHAPTERS":
        subj_name = p.get("subject", "")
        parent_name = p.get("parent_name", "")
        chapters_list = p.get("chapters", [])
        subj = db.query(Subject).filter(Subject.user_id == user.id, Subject.name == subj_name).first()
        if not subj: return f"Subject '{subj_name}' not found"

        # Resolve explicit parent
        explicit_parent_id = None
        if parent_name:
            parent = db.query(Chapter).filter(Chapter.subject_id == subj.id, Chapter.name == parent_name).first()
            if not parent: return f"Parent chapter '{parent_name}' not found"
            explicit_parent_id = parent.id

        base_order = db.query(func.max(Chapter.order_index)).filter(
            Chapter.subject_id == subj.id, Chapter.parent_chapter_id == explicit_parent_id
        ).scalar() or 0

        created = []
        leaf_ids = []

        # Auto-parenting: track the last chapter at each level
        # e.g. if we create Ch1(L1) then Sec1.1(L2) then Sec1.2(L2),
        # Sec1.1 and Sec1.2 auto-parent to Ch1
        last_at_level = {}  # level -> chapter_id

        for i, ch_data in enumerate(chapters_list):
            name = ch_data.get("name", "")
            if not name: continue

            level = ch_data.get("level", 3)

            # Determine parent: explicit > auto-inferred from batch order
            parent_id = explicit_parent_id
            if not parent_id:
                # Auto-infer: find the nearest higher-level chapter
                for lvl in range(level - 1, 0, -1):
                    if lvl in last_at_level:
                        parent_id = last_at_level[lvl]
                        break

            # Determine is_leaf: a chapter is leaf if no later chapter in this batch
            # has it as a parent (i.e., no deeper chapter follows in the same branch)
            is_leaf = True
            for j in range(i + 1, len(chapters_list)):
                later = chapters_list[j]
                later_level = later.get("level", 3)
                if later_level > level:
                    # A deeper chapter follows — check if it's in our subtree
                    # (levels increase by 1 per nesting depth)
                    is_leaf = False
                    break
                elif later_level <= level:
                    # Same or higher level — we're done with this subtree
                    break

            # Explicit is_leaf override from AI
            if "is_leaf" in ch_data:
                is_leaf = ch_data["is_leaf"]

            # Leaf chapters should always be level 3 in our system
            if is_leaf:
                level = 3

            ch = Chapter(
                subject_id=subj.id, name=name, level=level,
                parent_chapter_id=parent_id, order_index=base_order + i + 1,
                is_leaf=is_leaf,
            )
            db.add(ch); db.flush()
            last_at_level[level] = ch.id
            created.append(f"  {name} (L{level}, leaf={is_leaf})")
            if is_leaf:
                leaf_ids.append((ch.id, ch.name))

        db.commit()

        # Auto-trigger background generation for leaf chapters
        bg_lessons = 0
        bg_questions = 0
        for ch_id, ch_name in leaf_ids:
            asyncio.create_task(_assistant_bg_lesson(ch_id, ch_name, subj.name, subj.prompt_style, user_api_key))
            bg_lessons += 1
            asyncio.create_task(_assistant_bg_questions(ch_id, subj.name, ch_name, 8, subj.prompt_style, user_api_key))
            bg_questions += 1

        summary = f"Batch-created {len(created)} chapters under '{subj_name}':\n" + "\n".join(created)
        if bg_lessons:
            summary += f"\n\n⏳ Auto-started lesson generation for {bg_lessons} leaf chapters"
        if bg_questions:
            summary += f"\n⏳ Auto-started question generation for {bg_questions} leaf chapters"
        return summary

    if t == "DELETE_SUBJECT":
        name = p.get("name", "")
        subj = db.query(Subject).filter(Subject.user_id == user.id, Subject.name == name).first()
        if not subj: return f"Subject '{name}' not found"
        ch_count = db.query(func.count(Chapter.id)).filter(Chapter.subject_id == subj.id).scalar()
        q_count = db.query(func.count(Question.id)).filter(Question.subject_id == subj.id).scalar()
        db.query(Question).filter(Question.subject_id == subj.id).delete()
        db.query(Chapter).filter(Chapter.subject_id == subj.id).delete()
        db.delete(subj); db.commit()
        return f"Deleted subject '{name}' ({ch_count} chapters, {q_count} questions)"

    if t == "DELETE_CHAPTER":
        subj_name = p.get("subject", "")
        ch_name = p.get("name", "")
        subj = db.query(Subject).filter(Subject.user_id == user.id, Subject.name == subj_name).first()
        if not subj: return f"Subject '{subj_name}' not found"
        ch = db.query(Chapter).filter(Chapter.subject_id == subj.id, Chapter.name == ch_name).first()
        if not ch: return f"Chapter '{ch_name}' not found"
        q_count = db.query(func.count(Question.id)).filter(Question.chapter_id == ch.id).scalar()
        db.query(Question).filter(Question.chapter_id == ch.id).delete()
        db.delete(ch); db.commit()
        return f"Deleted chapter '{ch_name}' ({q_count} questions)"

    if t == "RENAME_SUBJECT":
        old_name = p.get("old_name", ""); new_name = p.get("new_name", "")
        subj = db.query(Subject).filter(Subject.user_id == user.id, Subject.name == old_name).first()
        if not subj: return f"Subject '{old_name}' not found"
        if db.query(Subject).filter(Subject.user_id == user.id, Subject.name == new_name).first():
            return f"Subject '{new_name}' already exists"
        subj.name = new_name; db.commit()
        return f"Renamed '{old_name}' to '{new_name}'"

    if t == "LIST_SUBJECTS":
        subs = db.query(Subject).filter(Subject.user_id == user.id, Subject.is_active == True).all()
        if not subs: return "No subjects"
        lines = ["Current subjects:"]
        for s in subs:
            ch_count = db.query(func.count(Chapter.id)).filter(Chapter.subject_id == s.id).scalar()
            q_count = db.query(func.count(Question.id)).filter(Question.subject_id == s.id).scalar()
            lines.append(f"- {s.name} ({ch_count} chapters, {q_count} questions)")
        return "\n".join(lines)

    if t == "LIST_CHAPTERS":
        subj_name = p.get("subject", "")
        subj = db.query(Subject).filter(Subject.user_id == user.id, Subject.name == subj_name).first()
        if not subj: return f"Subject '{subj_name}' not found"

        def build_tree(parent_id=None, indent=0):
            lines = []
            chs = db.query(Chapter).filter(
                Chapter.subject_id == subj.id, Chapter.parent_chapter_id == parent_id
            ).order_by(Chapter.order_index).all()
            for ch in chs:
                prefix = "  " * indent + ("+ " if indent > 0 else "")
                q_count = db.query(func.count(Question.id)).filter(Question.chapter_id == ch.id).scalar()
                leaf = "[L]" if ch.is_leaf else "[D]"
                cached = " cached" if (ch.description and ch.description.startswith("讲义/")) else ""
                lines.append(f"{prefix}{leaf} {ch.name} (L{ch.level}, {q_count}q{cached})")
                lines.extend(build_tree(ch.id, indent + 1))
            return lines

        tree = build_tree()
        if not tree:
            return f"No chapters in '{subj_name}'"
        return "Chapter tree for '" + subj_name + "':\n" + "\n".join(tree)

    if t == "WRONG_SUMMARY":
        wrongs = db.query(WrongBook).filter(WrongBook.user_id == user.id).order_by(
            WrongBook.last_wrong_at.desc()).limit(10).all()
        if not wrongs: return "No wrong answers"
        lines = ["Recent wrong answers:"]
        for w in wrongs:
            q = db.query(Question).filter_by(id=w.question_id).first()
            c = json.loads(q.content_json) if q else {}
            lines.append(f"- [{w.wrong_count}x] {c.get('question_text', '?')[:60]}")
        return "\n".join(lines)

    # ── P0: Generation tools ──

    if t == "GENERATE_QUESTIONS":
        subj_name = p.get("subject", ""); ch_name = p.get("chapter", "")
        count = p.get("count", 5); q_type = p.get("type", "single_choice")
        subj = db.query(Subject).filter(Subject.user_id == user.id, Subject.name == subj_name).first()
        if not subj: return f"Subject '{subj_name}' not found"
        ch = db.query(Chapter).filter(Chapter.subject_id == subj.id, Chapter.name == ch_name).first()
        if not ch: return f"Chapter '{ch_name}' not found in '{subj_name}'"
        gen_result = await generate_questions(
            subject_name=subj.name, chapter_name=ch.name,
            count=min(count, 10), difficulty_range=(1, 5),
            prompt_style=subj.prompt_style, api_key=user_api_key,
        )
        created = 0
        for q_data in gen_result:
            q = Question(
                subject_id=subj.id, chapter_id=ch.id,
                question_type=q_data.get("question_type", q_type),
                content_json=json.dumps(q_data.get("content_json", {}), ensure_ascii=False),
                difficulty=q_data.get("difficulty", 1),
                has_latex=q_data.get("has_latex", False),
                created_by="ai_assistant",
            )
            db.add(q); created += 1
        db.commit()
        return f"Generated {created} questions for '{ch_name}' under '{subj_name}'"

    if t == "GENERATE_LESSON":
        subj_name = p.get("subject", ""); ch_name = p.get("chapter", "")
        subj = db.query(Subject).filter(Subject.user_id == user.id, Subject.name == subj_name).first()
        if not subj: return f"Subject '{subj_name}' not found"
        ch = db.query(Chapter).filter(Chapter.subject_id == subj.id, Chapter.name == ch_name).first()
        if not ch: return f"Chapter '{ch_name}' not found in '{subj_name}'"
        content = await generate_lesson_content(
            chapter_name=ch.name, subject_name=subj.name,
            prompt_style=subj.prompt_style, api_key=user_api_key,
        )
        ch.description = content
        db.commit()
        return f"Lesson content generated for '{ch_name}' ({len(content)} chars)"

    if t == "GENERATE_SIMILAR":
        subj_name = p.get("subject", ""); ch_name = p.get("chapter", "")
        ref_text = p.get("reference_question", "")
        subj = db.query(Subject).filter(Subject.user_id == user.id, Subject.name == subj_name).first()
        if not subj: return f"Subject '{subj_name}' not found"
        ch = db.query(Chapter).filter(Chapter.subject_id == subj.id, Chapter.name == ch_name).first()
        if not ch: return f"Chapter '{ch_name}' not found in '{subj_name}'"
        q_data = await generate_similar_question(
            question_text=ref_text, question_type="single_choice",
            subject_name=subj.name, chapter_name=ch.name, difficulty=3,
            api_key=user_api_key,
        )
        q = Question(
            subject_id=subj.id, chapter_id=ch.id,
            question_type=q_data.get("question_type", "single_choice"),
            content_json=json.dumps(q_data.get("content_json", {}), ensure_ascii=False),
            difficulty=q_data.get("difficulty", 3),
            has_latex=q_data.get("has_latex", False),
            created_by="ai_assistant",
        )
        db.add(q); db.commit()
        return f"Generated 1 similar question for '{ch_name}'"

    # ── P1: Analysis tools ──

    if t == "ANALYZE_MASTERY":
        subj_name = p.get("subject", "")
        subj = db.query(Subject).filter(Subject.user_id == user.id, Subject.name == subj_name).first()
        if not subj: return f"Subject '{subj_name}' not found"
        records = db.query(ChapterMastery).filter(ChapterMastery.user_id == user.id).join(
            Chapter, ChapterMastery.chapter_id == Chapter.id
        ).filter(Chapter.subject_id == subj.id).all()
        if not records: return f"No mastery data for '{subj_name}' yet"
        lines = [f"Mastery for '{subj_name}':"]
        for r in sorted(records, key=lambda r: r.mastery_score or 0):
            ch = db.query(Chapter).filter_by(id=r.chapter_id).first()
            name = ch.name if ch else f"Ch#{r.chapter_id}"
            stars = r.star_level or 0
            score = r.mastery_score or 0
            stars_str = "⭐" * stars + "☆" * (5 - stars)
            lines.append(f"  {stars_str} {name} — score {score:.0%}, {r.total_attempts} attempts")
        return "\n".join(lines)

    if t == "DASHBOARD":
        subj_count = db.query(func.count(Subject.id)).filter(Subject.user_id == user.id, Subject.is_active == True).scalar()
        ch_count = db.query(func.count(Chapter.id)).join(Subject).filter(Subject.user_id == user.id).scalar()
        q_count = db.query(func.count(Question.id)).join(Subject).filter(Subject.user_id == user.id).scalar()
        sess_count = db.query(func.count(PracticeSession.id)).filter(PracticeSession.user_id == user.id).scalar()
        wrong_count = db.query(func.count(WrongBook.id)).filter(WrongBook.user_id == user.id).scalar()
        vocab_count = db.query(func.count(VocabCard.id)).filter(VocabCard.user_id == user.id).scalar()
        return (
            f"Dashboard:\n"
            f"- Subjects: {subj_count}\n"
            f"- Chapters: {ch_count}\n"
            f"- Questions: {q_count}\n"
            f"- Practice sessions: {sess_count}\n"
            f"- Wrong answers: {wrong_count}\n"
            f"- Vocab cards: {vocab_count}"
        )

    if t == "SEARCH_MATERIALS":
        from app.services.rag_engine import search_materials as rag_search
        query = p.get("query", "")
        if not query: return "ERROR: query required"
        try:
            results = await rag_search(user.id, query, user_api_key or user.api_key)
        except Exception as e:
            return f"RAG search failed: {str(e)[:100]}"
        if not results:
            return "未找到相关资料。建议上传教材或笔记后再搜索。"
        lines = ["找到以下相关资料："]
        for i, r in enumerate(results):
            lines.append(f"\n**{i+1}.** [{r['source']}] (相关度: {r['score']})\n{r['text'][:300]}")
        return "\n".join(lines)

    if t == "READ_MATERIAL":
        filename = p.get("filename", "")
        if not filename: return "ERROR: filename required"
        from app.services.vault_manager import get_vault
        vault = get_vault(user.id)
        content = vault.read(f"素材/{filename}")
        if not content:
            return f"文件 '{filename}' 不存在"
        return content[:3000]  # Truncate for safety

    return f"Unknown action: {t}"


# Slow actions that invoke AI generation — run as background tasks
_BG_ACTIONS = {"GENERATE_QUESTIONS", "GENERATE_LESSON", "GENERATE_SIMILAR"}
_bg_semaphore = asyncio.Semaphore(3)  # limit concurrent BG AI + DB tasks


async def _bg_execute(action: dict, user_id: int):
    """Execute a slow action in background with its own DB session."""
    from app.db.engine import SessionLocal
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if user:
            await _execute_action(action, user, db, user.api_key)
    except Exception as e:
        import logging
        logging.getLogger("uvicorn.error").warning(f"BG action {action['type']} failed: {e}")
    finally:
        db.close()


def _get_chapter_path(db: Session, chapter_id: int) -> tuple[str, list[str]]:
    """Resolve full hierarchical path for a chapter with order-index prefixes.

    Returns: (subject_name, path_components) like ("高等数学", ["01_第一章", "§1.1_节名", "01_课时名"])
    """
    from app.db.models import Subject
    ch = db.query(Chapter).filter_by(id=chapter_id).first()
    if not ch:
        return ("", [])
    subj = db.query(Subject).filter_by(id=ch.subject_id).first()
    subject_name = subj.name if subj else ""
    # Walk up parent chain, prefixing each with order_index
    parts = [(ch.order_index, ch.name)]
    current = ch
    while current.parent_chapter_id:
        parent = db.query(Chapter).filter_by(id=current.parent_chapter_id).first()
        if not parent:
            break
        parts.insert(0, (parent.order_index, parent.name))
        current = parent
    # Format: pad order to 2 digits, e.g. "01_第一章"
    formatted = []
    for i, (order_idx, name) in enumerate(parts):
        if i < len(parts) - 1:
            # Parent levels get order prefix for sorting
            formatted.append(f"{order_idx:02d}_{name}")
        else:
            # Leaf level (the file itself) — keep name as-is (it may already contain order info)
            formatted.append(name)
    return (subject_name, formatted)


async def _assistant_bg_lesson(chapter_id: int, chapter_name: str, subject_name: str, prompt_style: str | None, api_key: str | None = None):
    """Background: generate and cache lesson content for a chapter. Also writes to vault."""
    async with _bg_semaphore:
        from app.db.engine import SessionLocal
        db = SessionLocal()
        try:
            full = ""
            async for chunk in generate_lesson_content_stream(
                chapter_name=chapter_name, subject_name=subject_name,
                prompt_style=prompt_style, api_key=api_key,
            ):
                full += chunk
            if full:
                ch = db.query(Chapter).filter_by(id=chapter_id).first()
                if ch:
                    from app.services.vault_manager import get_vault
                    # Resolve full hierarchy: 章/节/课时
                    subj_name, path_parts = _get_chapter_path(db, chapter_id)
                    if subj_name and path_parts:
                        # Get user_id from chapter's subject
                        subj = db.query(Subject).filter_by(id=ch.subject_id).first()
                        if subj:
                            vault = get_vault(subj.user_id)
                            vault_path = vault.lesson_path(subj_name, path_parts)
                            vault.write(vault_path, full)
                            ch.description = vault_path
                    db.commit()
        except Exception as e:
            import logging
            logging.getLogger("uvicorn.error").warning(f"Asst BG lesson failed ch{chapter_id}: {e}")
        finally:
            db.close()


async def _assistant_bg_questions(chapter_id: int, subject_name: str, chapter_name: str, count: int, prompt_style: str | None, api_key: str | None = None):
    """Background: generate questions for a chapter."""
    async with _bg_semaphore:
        from app.db.engine import SessionLocal
        db = SessionLocal()
        try:
            ch = db.query(Chapter).filter_by(id=chapter_id).first()
            if not ch: return
            generated = await generate_questions(
                subject_name=subject_name, chapter_name=chapter_name,
                count=count, difficulty_range=(1, 5), prompt_style=prompt_style,
                api_key=api_key,
            )
            for q_data in generated:
                q = Question(
                    subject_id=ch.subject_id, chapter_id=ch.id,
                    question_type=q_data.get("question_type", "single_choice"),
                    content_json=json.dumps(q_data.get("content_json", {}), ensure_ascii=False),
                    difficulty=q_data.get("difficulty", 1),
                    has_latex=q_data.get("has_latex", False),
                    created_by="ai_assistant",
                )
                db.add(q)
            db.commit()
        except Exception as e:
            import logging
            logging.getLogger("uvicorn.error").warning(f"Asst BG questions failed ch{chapter_id}: {e}")
        finally:
            db.close()

@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    messages = body.messages
    if not messages:
        raise HTTPException(status_code=400, detail="No messages")

    # ── Skill Router + Context Budget ──
    from app.services.skill_router import route_skill, get_skill_prompt, get_fallback_message, log_routing
    from app.services.vault_manager import get_vault
    from app.services.agent_context import build_agent_context

    vault = get_vault(user.id)
    last_msg = messages[-1]["content"] if messages else ""
    skill_name, skill_trigger = route_skill(last_msg)

    skill_prompt_text = None
    if skill_name:
        skill_prompt_text = get_skill_prompt(skill_name, vault.root)
        log_routing(last_msg, skill_name, False)

    # Build context: STABLE prefix first (DeepSeek auto-cache), DYNAMIC data last
    ctx = _build_context(user, db)
    dynamic_block = f"\n\n## Current User Data\n{ctx}"
    if body.page_context:
        dynamic_block += f"\n\n## Page Context\n{body.page_context}"

    agent_ctx = build_agent_context(vault, skill_prompt=skill_prompt_text)
    if agent_ctx:
        sys_msg = SYSTEM_PROMPT_BASE + "\n\n---\n\n" + agent_ctx + dynamic_block
    else:
        sys_msg = SYSTEM_PROMPT_BASE + (("\n\n---\n\n" + skill_prompt_text) if skill_prompt_text else "") + dynamic_block

    full_messages = [{"role": "system", "content": sys_msg}] + messages
    client = _get_model_client(user, body.model)

    # ── Multi-step Agent Loop (Think → Act → Observe → Respond) ──
    MAX_ITERATIONS = 5
    all_actions = []
    raw = ""
    conv_messages = list(full_messages)  # mutable copy for tool result injection

    for iteration in range(MAX_ITERATIONS):
        raw = await client.generate(conv_messages, temperature=0.7, max_tokens=2000, model="deepseek-chat")
        actions = _parse_actions(raw)

        # Separate: fast actions (execute now) vs BG actions (fire-and-forget)
        fast_actions = [a for a in actions if a["type"] not in _BG_ACTIONS]
        bg_actions = [a for a in actions if a["type"] in _BG_ACTIONS]

        # Fire BG actions
        for a in bg_actions:
            asyncio.create_task(_bg_execute(a, user.id))
            all_actions.append(f"⏳ {a['type']} started in background")

        # Execute fast actions inline
        if not fast_actions:
            break  # No more tools to call → final response

        tool_results = []
        for a in fast_actions:
            result = await _execute_action(a, user, db, user.api_key)
            all_actions.append(result)
            tool_results.append(f"[TOOL RESULT: {a['type']}]\n{result}")

        # Feed tool results back into conversation for next iteration
        conv_messages.append({"role": "assistant", "content": raw})
        conv_messages.append({"role": "user", "content": "Tool results:\n" + "\n\n".join(tool_results) + "\n\nContinue based on these results. If you have enough information, give your final answer. If you need more tools, use [ACTION:...] tags."})

    clean = re.sub(r'\[ACTION:\w+\].*?\[/ACTION\]', '', raw, flags=re.DOTALL).strip()
    return ChatResponse(reply=clean, actions=all_actions, context=ctx)


@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    messages = body.messages
    if not messages:
        raise HTTPException(status_code=400, detail="No messages")

    # ── Skill Router + Context Budget ──
    from app.services.skill_router import route_skill, get_skill_prompt, log_routing
    from app.services.vault_manager import get_vault
    from app.services.agent_context import build_agent_context

    vault = get_vault(user.id)
    last_msg = messages[-1]["content"] if messages else ""
    skill_name, skill_trigger = route_skill(last_msg)

    skill_prompt_text = None
    if skill_name:
        skill_prompt_text = get_skill_prompt(skill_name, vault.root)
        log_routing(last_msg, skill_name, False)

    # Build context: STABLE prefix first (DeepSeek auto-cache), DYNAMIC data last
    user_ctx = _build_context(user, db)
    dynamic_block = f"\n\n## Current User Data\n{user_ctx}"
    if body.page_context:
        dynamic_block += f"\n\n## Page Context\n{body.page_context}"

    agent_ctx = build_agent_context(vault, skill_prompt=skill_prompt_text)
    if agent_ctx:
        sys_msg = SYSTEM_PROMPT_BASE + "\n\n---\n\n" + agent_ctx + dynamic_block
    else:
        sys_msg = SYSTEM_PROMPT_BASE + (("\n\n---\n\n" + skill_prompt_text) if skill_prompt_text else "") + dynamic_block

    full_messages = [{"role": "system", "content": sys_msg}] + messages

    async def event_stream():
        MAX_ITERATIONS = 5
        conv_messages = list(full_messages)
        all_results = []

        try:
            client = _get_model_client(user, body.model)
            for iteration in range(MAX_ITERATIONS):
                # Stream text response
                full_response = ""
                async for chunk in client.generate_stream(
                    conv_messages, temperature=0.7, max_tokens=2000, model="deepseek-chat"
                ):
                    full_response += chunk
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                    await asyncio.sleep(0.01)

                yield f"data: {json.dumps({'text_done': True})}\n\n"

                actions = _parse_actions(full_response)
                fast_actions = [a for a in actions if a["type"] not in _BG_ACTIONS]
                bg_actions = [a for a in actions if a["type"] in _BG_ACTIONS]

                for a in bg_actions:
                    asyncio.create_task(_bg_execute(a, user.id))
                    all_results.append(f"⏳ {a['type']} started in background")

                if not fast_actions:
                    break  # No more tools → done

                # Execute fast tools and feed results back
                tool_results = []
                for a in fast_actions:
                    atype = a["type"]
                    # Send action as a collapsible tool-call event (not raw text)
                    label_map = {
                        "SEARCH_MATERIALS": "搜索资料",
                        "READ_MATERIAL": "读取文件",
                        "LIST_SUBJECTS": "列出科目",
                        "LIST_CHAPTERS": "列出章节",
                        "ADD_SUBJECT": "添加科目",
                        "ADD_CHAPTER": "添加章节",
                        "BATCH_ADD_CHAPTERS": "批量添加章节",
                        "FILL_CHAPTER": "填充章节内容",
                        "DASHBOARD": "查看数据",
                        "WRONG_SUMMARY": "查看错题",
                        "ANALYZE_MASTERY": "分析掌握度",
                    }
                    label = label_map.get(atype, atype)
                    yield f"data: {json.dumps({'tool_start': True, 'tool': atype, 'label': label})}\n\n"
                    try:
                        r = await _execute_action(a, user, db, user.api_key)
                        all_results.append(r)
                        tool_results.append(f"[TOOL RESULT: {atype}]\n{r}")
                        # Send tool result as collapsible event (summary only, full text hidden)
                        summary = r[:80].replace('\n', ' ') + ('...' if len(r) > 80 else '')
                        yield f"data: {json.dumps({'tool_end': True, 'tool': atype, 'summary': summary, 'full': r})}\n\n"
                    except Exception as e:
                        all_results.append(f"ERROR: {str(e)[:200]}")
                        tool_results.append(f"[TOOL ERROR: {atype}]\n{str(e)[:200]}")
                        yield f"data: {json.dumps({'tool_end': True, 'tool': atype, 'summary': '执行失败: ' + str(e)[:80], 'error': True})}\n\n"

                # Feed back for next iteration
                conv_messages.append({"role": "assistant", "content": full_response})
                conv_messages.append({"role": "user", "content": "Tool results:\n" + "\n\n".join(tool_results) + "\n\nContinue. If done, give final answer without [ACTION] tags."})

            yield f"data: {json.dumps({'done': True, 'actions': all_results})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/chat/follow-up")
async def chat_follow_up(
    body: FollowUpRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Ask a follow-up question about a specific question's explanation, with full context."""
    # Build rich context from the question + previous explanation
    ctx = _build_context(user, db)
    context_block = (
        f"You are helping a student understand a question they got wrong or need help with.\n\n"
        f"=== QUESTION ===\n{body.question_text}\n\n"
        f"=== STUDENT'S ANSWER ===\n{body.user_answer}\n\n"
        f"=== CORRECT ANSWER ===\n{body.correct_answer}\n\n"
        f"=== PREVIOUS EXPLANATION ===\n{body.explanation}\n\n"
        f"=== FOLLOW-UP QUESTION ===\n{body.follow_up}\n\n"
        f"Reply concisely in Chinese Markdown. Refer to specific parts of the question and explanation. "
        f"Help the student understand deeply."
    )

    messages = [{"role": "user", "content": context_block}]

    async def event_stream():
        try:
            client = _get_model_client(user, "deepseek")  # follow-up always uses DeepSeek for consistency
            async for chunk in client.generate_stream(
                messages, temperature=0.7, max_tokens=2000, model="deepseek-chat"
            ):
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                await asyncio.sleep(0.01)
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
