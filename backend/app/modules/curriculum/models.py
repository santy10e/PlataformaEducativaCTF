"""Curriculum tables: course → module → lesson → activity (SPEC §5, §9)."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models import ID_TYPE, Category, Difficulty, SchoolClass, Timestamped, User

COURSE_STATUSES = ("DRAFT", "PUBLISHED", "ARCHIVED")
PROGRESS_STATUSES = ("NOT_STARTED", "IN_PROGRESS", "PENDING_REVIEW", "NEEDS_CHANGES", "APPROVED", "REJECTED")

course_classes = Table(
    "course_classes",
    Base.metadata,
    Column("course_id", ID_TYPE, ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True),
    Column("class_id", ID_TYPE, ForeignKey("classes.id", ondelete="CASCADE"), primary_key=True),
)
activity_prerequisites = Table(
    "activity_prerequisites",
    Base.metadata,
    Column("activity_id", ID_TYPE, ForeignKey("activities.id", ondelete="CASCADE"), primary_key=True),
    Column("required_activity_id", ID_TYPE, ForeignKey("activities.id", ondelete="CASCADE"), primary_key=True),
)


class Course(Timestamped, Base):
    __tablename__ = "courses"
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT", index=True)
    # NULL owner = shared template managed by administrators (e.g. the seeded 9-month plan).
    owner_user_id: Mapped[int | None] = mapped_column(ID_TYPE, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), index=True)
    owner: Mapped[User | None] = relationship()
    classes: Mapped[list[SchoolClass]] = relationship(secondary=course_classes)
    modules: Mapped[list["CourseModule"]] = relationship(back_populates="course", order_by="CourseModule.sort_order, CourseModule.id")


class CourseModule(Timestamped, Base):
    __tablename__ = "modules"
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    deleted_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), index=True)
    course: Mapped[Course] = relationship(back_populates="modules")
    lessons: Mapped[list["Lesson"]] = relationship(back_populates="module", order_by="Lesson.sort_order, Lesson.id")


class Lesson(Timestamped, Base):
    __tablename__ = "lessons"
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    module_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("modules.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    deleted_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), index=True)
    module: Mapped[CourseModule] = relationship(back_populates="lessons")
    activities: Mapped[list["Activity"]] = relationship(back_populates="lesson", order_by="Activity.sort_order, Activity.id")


class Activity(Timestamped, Base):
    __tablename__ = "activities"
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    lesson_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    category_id: Mapped[int | None] = mapped_column(ID_TYPE, ForeignKey("categories.id", ondelete="RESTRICT"), index=True)
    difficulty_id: Mapped[int | None] = mapped_column(ID_TYPE, ForeignKey("difficulties.id", ondelete="RESTRICT"), index=True)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT", index=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    deleted_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), index=True)
    lesson: Mapped[Lesson] = relationship(back_populates="activities")
    category: Mapped[Category | None] = relationship()
    difficulty: Mapped[Difficulty | None] = relationship()
    prerequisites: Mapped[list["Activity"]] = relationship(
        secondary=activity_prerequisites,
        primaryjoin=id == activity_prerequisites.c.activity_id,
        secondaryjoin=id == activity_prerequisites.c.required_activity_id,
    )
    hints: Mapped[list["ActivityHint"]] = relationship(back_populates="activity", cascade="all, delete-orphan", order_by="ActivityHint.order")


class ActivityHint(Timestamped, Base):
    __tablename__ = "activity_hints"
    __table_args__ = (UniqueConstraint("activity_id", "order", name="uq_activity_hint_order"),)
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    activity: Mapped[Activity] = relationship(back_populates="hints")


class HintUsage(Timestamped, Base):
    __tablename__ = "hint_usage"
    __table_args__ = (UniqueConstraint("user_id", "hint_id", name="uq_hint_usage_user_hint"),)
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True)
    hint_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("activity_hints.id", ondelete="CASCADE"), nullable=False)
    cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ActivityProgress(Timestamped, Base):
    __tablename__ = "activity_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "activity_id", name="uq_activity_progress_user_activity"),
        Index("ix_activity_progress_status_submitted", "status", "submitted_at"),
    )
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="IN_PROGRESS")
    started_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    submitted_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    completed_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score: Mapped[int | None] = mapped_column(Integer)
    max_score: Mapped[int | None] = mapped_column(Integer)
    # The learner's latest answer (quiz choices, exercise text, project text/URL); never contains solutions.
    submission: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    feedback: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ID_TYPE, ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    auto_graded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    activity: Mapped[Activity] = relationship()
    user: Mapped[User] = relationship(foreign_keys=[user_id])
