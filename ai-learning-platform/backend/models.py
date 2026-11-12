from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(190), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Roadmap(Base):
    __tablename__ = "roadmaps"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    level: Mapped[str] = mapped_column(String(30), index=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Module(Base):
    __tablename__ = "modules"
    id: Mapped[int] = mapped_column(primary_key=True)
    module_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    roadmap_id: Mapped[int] = mapped_column(ForeignKey("roadmaps.id"), index=True)
    order_index: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(250))
    phase: Mapped[str] = mapped_column(String(150))
    prerequisites: Mapped[list] = mapped_column(JSON, default=list)  # list of module_id strings
    track_eligibility: Mapped[list] = mapped_column(JSON, default=list)
    interview_weightage: Mapped[int] = mapped_column(Integer, default=50)  # 1-100 (exam/interview weightage)
    theoretical_importance: Mapped[int] = mapped_column(Integer, default=5)  # 1-10
    future_scope: Mapped[float] = mapped_column(Float, default=5.0)  # 1-10
    estimated_time_minutes: Mapped[int] = mapped_column(Integer, default=40)
    content: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # filled lazily by the LLM
    youtube_keywords: Mapped[list] = mapped_column(JSON, default=list)
    vector_index_namespace: Mapped[str] = mapped_column(String(100), index=True)


class Progress(Base):
    __tablename__ = "progress"
    __table_args__ = (UniqueConstraint("user_id", "module_pk", name="uq_user_module"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    module_pk: Mapped[int] = mapped_column(ForeignKey("modules.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")  # in_progress | mastered
    best_score: Mapped[float] = mapped_column(Float, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)


class Quiz(Base):
    __tablename__ = "quizzes"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    module_pk: Mapped[int] = mapped_column(ForeignKey("modules.id"), index=True)
    questions: Mapped[list] = mapped_column(JSON)  # includes answers (never sent to the browser)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    module_pk: Mapped[int] = mapped_column(ForeignKey("modules.id"), index=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id"))
    score: Mapped[float] = mapped_column(Float)
    breakdown: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Chunk(Base):
    """Vector store: one row per text chunk, scoped by module namespace."""

    __tablename__ = "chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    namespace: Mapped[str] = mapped_column(String(100), index=True)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
