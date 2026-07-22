"""SQLAlchemy declarative models — 9 tables for the quiz application."""

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey, UniqueConstraint, JSON
)
from sqlalchemy.orm import relationship

from app.db.base import Base, utcnow


# ──────────────────────────────────────────────
# 1. users
# ──────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user")  # user / admin / superadmin
    api_key = Column(String(255), nullable=True)  # per-user DeepSeek key
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    @property
    def api_key_masked(self) -> str | None:
        if not self.api_key:
            return None
        return self.api_key[:11] + "..." + self.api_key[-4:] if len(self.api_key) > 15 else "***"

    mastery_records = relationship("ChapterMastery", back_populates="user")


# ──────────────────────────────────────────────
# 2. subjects
# ──────────────────────────────────────────────
class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, default=1)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    prompt_style = Column(Text, nullable=True)
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)

    chapters = relationship("Chapter", back_populates="subject", order_by="Chapter.order_index")
    questions = relationship("Question", back_populates="subject")


# ──────────────────────────────────────────────
# 3. chapters (supports 3-level nesting)
# ──────────────────────────────────────────────
class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    order_index = Column(Integer, nullable=False, default=0)
    parent_chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=True)
    level = Column(Integer, nullable=False, default=1)  # 1=章, 2=节, 3=课时
    is_leaf = Column(Boolean, default=False)  # True for level=3 nodes
    lesson_duration_minutes = Column(Integer, default=20)
    created_at = Column(DateTime, default=utcnow)

    subject = relationship("Subject", back_populates="chapters")
    children = relationship(
        "Chapter",
        backref="parent",
        remote_side=[id],
        order_by="Chapter.order_index",
    )
    questions = relationship("Question", back_populates="chapter")
    mastery_records = relationship("ChapterMastery", back_populates="chapter")


# ──────────────────────────────────────────────
# 4. questions
# ──────────────────────────────────────────────
class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    question_type = Column(String(30), nullable=False)
    # single_choice / multiple_choice / fill_blank / short_answer / calculation / proof
    content_json = Column(Text, nullable=False)  # JSON string
    difficulty = Column(Integer, nullable=False, default=1)  # 1-5
    has_latex = Column(Boolean, default=False)
    created_by = Column(String(30), default="ai_generated")  # seed / ai_generated / user_added
    source_question_id = Column(Integer, ForeignKey("questions.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    subject = relationship("Subject", back_populates="questions")
    chapter = relationship("Chapter", back_populates="questions")
    attempts = relationship("QuestionAttempt", back_populates="question")
    wrong_book_entry = relationship("WrongBook", back_populates="question", uselist=False)
    # Self-referential: one source question → many similar questions
    similar_questions = relationship(
        "Question",
        back_populates="source_question",
        foreign_keys=[source_question_id],
        order_by="Question.id",
    )
    source_question = relationship(
        "Question",
        back_populates="similar_questions",
        remote_side=[id],
        foreign_keys=[source_question_id],
        post_update=True,  # avoid circular dependency on insert
    )


# ──────────────────────────────────────────────
# 5. practice_sessions
# ──────────────────────────────────────────────
class PracticeSession(Base):
    __tablename__ = "practice_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, default=1)
    mode = Column(String(20), nullable=False)  # lesson / pure
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=True)
    started_at = Column(DateTime, default=utcnow)
    ended_at = Column(DateTime, nullable=True)
    is_completed = Column(Boolean, default=False)
    current_index = Column(Integer, default=0)
    questions_order = Column(Text, nullable=False, default="[]")  # JSON list of question IDs
    lesson_content = Column(Text, nullable=True)  # Markdown for lesson mode
    created_at = Column(DateTime, default=utcnow)

    attempts = relationship("QuestionAttempt", back_populates="session")


# ──────────────────────────────────────────────
# 6. question_attempts
# ──────────────────────────────────────────────
class QuestionAttempt(Base):
    __tablename__ = "question_attempts"
    __table_args__ = (
        UniqueConstraint("session_id", "question_id", name="uq_session_question"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("practice_sessions.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    user_answer = Column(Text, nullable=True)  # serialized answer
    is_correct = Column(Boolean, nullable=True)  # NULL = not yet answered
    time_spent_seconds = Column(Integer, nullable=True)
    attempted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    session = relationship("PracticeSession", back_populates="attempts")
    question = relationship("Question", back_populates="attempts")


# ──────────────────────────────────────────────
# 7. wrong_book
# ──────────────────────────────────────────────
class WrongBook(Base):
    __tablename__ = "wrong_book"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, default=1)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    first_wrong_at = Column(DateTime, nullable=False)
    last_wrong_at = Column(DateTime, nullable=False)
    wrong_count = Column(Integer, default=1)
    ai_explanation = Column(Text, nullable=True)
    user_note = Column(Text, nullable=True)
    mastery_status = Column(String(20), default="not_mastered")
    # not_mastered / reviewing / mastered
    bookmarked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (UniqueConstraint("user_id", "question_id", name="uq_user_question"),)

    question = relationship("Question", back_populates="wrong_book_entry")
    srs_schedule = relationship("SRSSchedule", back_populates="wrong_book", uselist=False)


# ──────────────────────────────────────────────
# 8. srs_schedule
# ──────────────────────────────────────────────
class SRSSchedule(Base):
    __tablename__ = "srs_schedule"

    id = Column(Integer, primary_key=True, autoincrement=True)
    wrong_book_id = Column(Integer, ForeignKey("wrong_book.id"), unique=True, nullable=False)
    next_review_at = Column(DateTime, nullable=False)
    interval_days = Column(Float, default=1.0)
    ease_factor = Column(Float, default=2.5)
    review_count = Column(Integer, default=0)
    last_review_at = Column(DateTime, nullable=True)
    last_performance = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    wrong_book = relationship("WrongBook", back_populates="srs_schedule")


# ──────────────────────────────────────────────
# 9. chapter_mastery
# ──────────────────────────────────────────────
class ChapterMastery(Base):
    __tablename__ = "chapter_mastery"
    __table_args__ = (
        UniqueConstraint("user_id", "chapter_id", name="uq_user_chapter_mastery"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, default=1)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    star_level = Column(Integer, default=0)  # 0-5
    mastery_score = Column(Float, default=0.0)  # 0-100
    accuracy_score = Column(Float, default=0.0)
    consistency_score = Column(Float, default=0.0)
    difficulty_score = Column(Float, default=0.0)
    speed_score = Column(Float, default=0.0)
    total_attempts = Column(Integer, default=0)
    correct_attempts = Column(Integer, default=0)
    last_calculated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="mastery_records")
    chapter = relationship("Chapter", back_populates="mastery_records")


# ──────────────────────────────────────────────
# 10. vocab_cards
# ──────────────────────────────────────────────
class VocabCard(Base):
    __tablename__ = "vocab_cards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, default=1)
    word = Column(String(200), nullable=False)
    definition = Column(Text, nullable=False)
    example_sentence = Column(Text, nullable=True)
    pronunciation = Column(String(200), nullable=True)
    root_analysis = Column(Text, nullable=True)       # 词根词缀分析
    synonyms = Column(Text, nullable=True)             # 近义词 (JSON array)
    antonyms = Column(Text, nullable=True)             # 反义词 (JSON array)
    collocations = Column(Text, nullable=True)         # 常见搭配 (JSON array)
    difficulty = Column(Integer, default=1)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True)
    created_by = Column(String(30), default="ai_generated")
    created_at = Column(DateTime, default=utcnow)


# ──────────────────────────────────────────────
# 11. vocab_reviews
# ──────────────────────────────────────────────
class VocabReview(Base):
    __tablename__ = "vocab_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vocab_card_id = Column(Integer, ForeignKey("vocab_cards.id"), unique=True, nullable=False)
    next_review_at = Column(DateTime, nullable=False)
    interval_days = Column(Float, default=1.0)
    ease_factor = Column(Float, default=2.5)
    review_count = Column(Integer, default=0)
    last_review_at = Column(DateTime, nullable=True)
    last_performance = Column(String(20), nullable=True)  # knew / fuzzy / forgot
    created_at = Column(DateTime, default=utcnow)

    card = relationship("VocabCard", backref="review")


# ──────────────────────────────────────────────
# 12. conversations (AI chat history)
# ──────────────────────────────────────────────
class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, default=1)
    title = Column(String(100), default="新对话")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    messages = relationship("ChatMessage", back_populates="conversation",
                            order_by="ChatMessage.created_at",
                            cascade="all, delete-orphan")


# ──────────────────────────────────────────────
# 13. chat_messages
# ──────────────────────────────────────────────
class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user / assistant / system
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    conversation = relationship("Conversation", back_populates="messages")


# ──────────────────────────────────────────────
# 14. note_materials (素材库 — clipped content snippets)
# ──────────────────────────────────────────────
class NoteMaterial(Base):
    __tablename__ = "note_materials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, default=1)
    content = Column(Text, nullable=False)  # HTML/Markdown with LaTeX
    source_url = Column(String(500), nullable=True)
    source_label = Column(String(200), nullable=True)  # e.g. "C++ 第一章"
    color_tag = Column(String(20), default="default")  # visual tag color
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)


# ──────────────────────────────────────────────
# 15. notes (笔记 — user-authored documents)
# ──────────────────────────────────────────────
class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, default=1)
    title = Column(String(200), default="无标题笔记")
    content = Column(Text, default="")  # Markdown with LaTeX
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True)
    is_pinned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
