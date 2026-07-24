"""Vocab router — vocabulary cards with SRS review."""
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.ai_service.client import DeepSeekClient
from app.db.engine import get_db
from app.db.models import VocabCard, VocabReview, Subject, User
from app.dependencies import get_current_user
from app.schemas.vocab import (
    VocabCardOut,
    VocabGenerateRequest,
    VocabReviewItem,
    VocabReviewRequest,
)
from app.services.srs_algorithm import sm2_calculate

router = APIRouter()


@router.get("", response_model=list[VocabCardOut])
def list_cards(
    subject_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(VocabCard).filter(VocabCard.user_id == current_user.id)
    if subject_id:
        q = q.filter(VocabCard.subject_id == subject_id)
    return q.order_by(VocabCard.created_at.desc()).limit(500).all()


@router.post("/generate", response_model=list[VocabCardOut])
async def generate_cards(
    body: VocabGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI-generate vocabulary cards with root analysis, synonyms, antonyms, collocations."""
    subject = db.query(Subject).filter_by(name=body.subject_name).first()

    client = DeepSeekClient(api_key=current_user.api_key)
    messages = [
        {"role": "system", "content": (
            "你是一位英语词汇教学专家，精通词根词缀分析。"
            "为每个单词提供完整的词汇学习卡片。返回严格JSON数组。"
        )},
        {"role": "user", "content": (
            f"请生成{body.count}个{body.subject_name}核心词汇卡片，难度{body.difficulty}/5。\n\n"
            f"每个单词必须包含以下字段（JSON格式）：\n"
            f"- word: 单词\n"
            f"- definition: 中文释义（简洁准确）\n"
            f"- pronunciation: 音标\n"
            f"- example_sentence: 英文例句（自然地道，贴合考试语境）\n"
            f"- root_analysis: 词根词缀分析，格式如「词根xxx=含义 + 前缀xxx=含义 → 字面含义 → 引申义」\n"
            f"- synonyms: 近义词列表，JSON数组如[\"word1\",\"word2\"]，附简要中文释义\n"
            f"- antonyms: 反义词列表，JSON数组如[\"word1\"]，附简要中文释义\n"
            f"- collocations: 常见搭配，JSON数组如[\"collocation1 中文\",\"collocation2 中文\"]\n\n"
            f"要求：\n"
            f"1. 词根分析要准确有据，不要编造\n"
            f"2. 词汇按难度递进排列，不要按字母序\n"
            f"3. 返回纯JSON数组，不要任何其他文字"
        )},
    ]
    raw = await client.generate(messages, temperature=0.7, max_tokens=4000)
    raw = raw.strip()
    if raw.startswith("```"): raw = raw.split("\n", 1)[1]
    if raw.endswith("```"): raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()

    try:
        cards_data = json.loads(raw)
        if isinstance(cards_data, dict): cards_data = [cards_data]
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI 生成解析失败，请重试")

    cards = []
    for c in cards_data:
        card = VocabCard(
            user_id=current_user.id,
            word=c.get("word", ""),
            definition=c.get("definition", ""),
            example_sentence=c.get("example_sentence", ""),
            pronunciation=c.get("pronunciation", ""),
            root_analysis=c.get("root_analysis", ""),
            synonyms=json.dumps(c.get("synonyms", []), ensure_ascii=False) if c.get("synonyms") else None,
            antonyms=json.dumps(c.get("antonyms", []), ensure_ascii=False) if c.get("antonyms") else None,
            collocations=json.dumps(c.get("collocations", []), ensure_ascii=False) if c.get("collocations") else None,
            difficulty=body.difficulty,
            subject_id=subject.id if subject else None,
            created_by="ai_generated",
        )
        db.add(card)
        db.flush()
        db.add(VocabReview(
            vocab_card_id=card.id,
            next_review_at=datetime.now(timezone.utc),
            interval_days=1.0,
        ))
        cards.append(card)
    db.commit()
    return [VocabCardOut.model_validate(c) for c in cards]


@router.delete("/{card_id}", status_code=204)
def delete_card(card_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    card = db.query(VocabCard).filter_by(id=card_id, user_id=current_user.id).first()
    if not card: raise HTTPException(status_code=404)
    review = db.query(VocabReview).filter_by(vocab_card_id=card_id).first()
    if review: db.delete(review)
    db.delete(card)
    db.commit()


@router.get("/review-today", response_model=list[VocabReviewItem])
def get_review_today(
    shuffle: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return cards due for review, shuffled by default."""
    now = datetime.now(timezone.utc)
    reviews = (
        db.query(VocabReview)
        .join(VocabCard, VocabReview.vocab_card_id == VocabCard.id)
        .filter(VocabReview.next_review_at <= now, VocabCard.user_id == current_user.id)
        .order_by(func.random() if shuffle else VocabReview.next_review_at)
        .all()
    )
    items = []
    for r in reviews:
        card = db.query(VocabCard).filter_by(id=r.vocab_card_id).first()
        if not card: continue
        items.append(VocabReviewItem(
            review_id=r.id,
            vocab_card_id=card.id,
            word=card.word,
            definition=card.definition,
            example_sentence=card.example_sentence,
            pronunciation=card.pronunciation,
            root_analysis=card.root_analysis,
            synonyms=card.synonyms,
            antonyms=card.antonyms,
            collocations=card.collocations,
            next_review_at=r.next_review_at,
            interval_days=r.interval_days,
            ease_factor=r.ease_factor,
            review_count=r.review_count,
        ))
    return items


@router.post("/review")
def submit_review(
    body: VocabReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.quality < 0 or body.quality > 5:
        raise HTTPException(status_code=400, detail="Quality must be 0-5")
    review = db.query(VocabReview).join(VocabCard).filter(
        VocabReview.vocab_card_id == body.vocab_card_id,
        VocabCard.user_id == current_user.id
    ).first()
    if not review: raise HTTPException(status_code=404)

    result = sm2_calculate(body.quality, review.interval_days, review.ease_factor, review.review_count)
    now = datetime.now(timezone.utc)
    review.interval_days = result["interval_days"]
    review.ease_factor = result["ease_factor"]
    review.review_count = result["review_count"]
    review.last_review_at = now
    review.next_review_at = now + timedelta(days=result["interval_days"])
    review.last_performance = {0: "forgot", 3: "fuzzy"}.get(body.quality, "knew") if body.quality <= 3 else "knew"
    db.commit()
    return {"status": "ok", "next_review_at": review.next_review_at.isoformat(), "interval_days": review.interval_days}
