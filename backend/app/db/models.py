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
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    mastery_records = relationship("ChapterMastery", back_populates="user")


# ──────────────────────────────────────────────
# 2. subjects
# ──────────────────────────────────────────────
class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    prompt_style = Column(Text, nullable=True)  # per-subject AI prompt customization
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
    question_id = Column(Integer, ForeignKey("questions.id"), unique=True, nullable=False)
    first_wrong_at = Column(DateTime, nullable=False)
    last_wrong_at = Column(DateTime, nullable=False)
    wrong_count = Column(Integer, default=1)
    ai_explanation = Column(Text, nullable=True)
    user_note = Column(Text, nullable=True)
    mastery_status = Column(String(20), default="not_mastered")
    # not_mastered / reviewing / mastered
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

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
    last_performance = Column(String(20), nullable=True)  # remembered / partial / forgot
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
