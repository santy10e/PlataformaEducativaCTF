from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

ID_TYPE = BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(Integer, "sqlite")

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ID_TYPE, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)
class_students = Table(
    "class_students",
    Base.metadata,
    Column("class_id", ID_TYPE, ForeignKey("classes.id", ondelete="CASCADE"), primary_key=True),
    Column("student_user_id", ID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ID_TYPE, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ID_TYPE, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False, server_default=func.now(), onupdate=func.now())


class User(Timestamped, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str | None] = mapped_column(String(254), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    roles: Mapped[list["Role"]] = relationship(secondary=user_roles, back_populates="users")
    student_profile: Mapped["StudentProfile | None"] = relationship(back_populates="user", cascade="all, delete-orphan", uselist=False)
    teacher_profile: Mapped["TeacherProfile | None"] = relationship(back_populates="user", cascade="all, delete-orphan", uselist=False)
    teaching_classes: Mapped[list["SchoolClass"]] = relationship(back_populates="teacher", foreign_keys="SchoolClass.teacher_user_id")
    enrolled_classes: Mapped[list["SchoolClass"]] = relationship(secondary=class_students, back_populates="students")


class Role(Timestamped, Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    users: Mapped[list[User]] = relationship(secondary=user_roles, back_populates="roles")
    permissions: Mapped[list["Permission"]] = relationship(secondary=role_permissions, back_populates="roles")


class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    roles: Mapped[list[Role]] = relationship(secondary=role_permissions, back_populates="permissions")


class Session(Timestamped, Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(512))


class SystemSetting(Timestamped, Base):
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[object] = mapped_column(JSON, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False, default="")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[int | None] = mapped_column(ID_TYPE, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(100))
    target_id: Mapped[str | None] = mapped_column(String(120))
    meta: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False, server_default=func.now(), index=True)


class StudentProfile(Base):
    __tablename__ = "student_profiles"
    user_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    user: Mapped[User] = relationship(back_populates="student_profile")


class TeacherProfile(Base):
    __tablename__ = "teacher_profiles"
    user_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    user: Mapped[User] = relationship(back_populates="teacher_profile")


class SchoolClass(Timestamped, Base):
    __tablename__ = "classes"
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    academic_period: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    description: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    teacher_user_id: Mapped[int | None] = mapped_column(ID_TYPE, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    teacher: Mapped[User | None] = relationship(back_populates="teaching_classes", foreign_keys=[teacher_user_id])
    students: Mapped[list[User]] = relationship(secondary=class_students, back_populates="enrolled_classes")


class ImportJob(Timestamped, Base):
    __tablename__ = "import_jobs"
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    actor_user_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="PREVIEWED")
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    preview_rows: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)


ctf_event_classes = Table(
    "ctf_event_classes", Base.metadata,
    Column("event_id", ID_TYPE, ForeignKey("ctf_events.id", ondelete="CASCADE"), primary_key=True),
    Column("class_id", ID_TYPE, ForeignKey("classes.id", ondelete="CASCADE"), primary_key=True),
)
challenge_prerequisites = Table(
    "challenge_prerequisites", Base.metadata,
    Column("challenge_id", ID_TYPE, ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True),
    Column("prerequisite_id", ID_TYPE, ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True),
)


class Category(Timestamped, Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#587666")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    challenges: Mapped[list["Challenge"]] = relationship(back_populates="category")


class Difficulty(Timestamped, Base):
    __tablename__ = "difficulties"
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(48), unique=True, nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#587666")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    challenges: Mapped[list["Challenge"]] = relationship(back_populates="difficulty")


class CtfEvent(Timestamped, Base):
    __tablename__ = "ctf_events"
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    mode: Mapped[str] = mapped_column(String(24), nullable=False, default="JEOPARDY")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="DRAFT", index=True)
    visibility: Mapped[str] = mapped_column(String(24), nullable=False, default="ASSIGNED")
    rules_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), index=True)
    classes: Mapped[list[SchoolClass]] = relationship(secondary=ctf_event_classes)
    challenges: Mapped[list["Challenge"]] = relationship(back_populates="event", cascade="all, delete-orphan")
    scoring_strategy: Mapped[str] = mapped_column(String(32), nullable=False, default="FIXED")
    scoring_config: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    max_attempts: Mapped[int | None] = mapped_column(Integer)
    scoreboard_frozen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Challenge(Timestamped, Base):
    __tablename__ = "challenges"
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    event_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("ctf_events.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True)
    difficulty_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("difficulties.id", ondelete="RESTRICT"), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="DRAFT", index=True)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delivery_type: Mapped[str] = mapped_column(String(24), nullable=False, default="STATIC")
    delivery_config: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    module_id: Mapped[str | None] = mapped_column(String(100))
    flag_hash: Mapped[str | None] = mapped_column(String(255))
    scoring_strategy: Mapped[str | None] = mapped_column(String(32))
    scoring_config: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    max_attempts: Mapped[int | None] = mapped_column(Integer)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), index=True)
    event: Mapped[CtfEvent] = relationship(back_populates="challenges")
    category: Mapped[Category] = relationship(back_populates="challenges")
    difficulty: Mapped[Difficulty] = relationship(back_populates="challenges")
    prerequisites: Mapped[list["Challenge"]] = relationship(secondary=challenge_prerequisites, primaryjoin=id == challenge_prerequisites.c.challenge_id, secondaryjoin=id == challenge_prerequisites.c.prerequisite_id)
    files: Mapped[list["ChallengeFile"]] = relationship(back_populates="challenge", cascade="all, delete-orphan")
    hints: Mapped[list["Hint"]] = relationship(back_populates="challenge", cascade="all, delete-orphan", order_by="Hint.order")



class ChallengeFlag(Timestamped, Base):
    __tablename__ = "challenge_flags"
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    challenge_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False, index=True)
    strategy: Mapped[str] = mapped_column(String(24), nullable=False)
    matcher: Mapped[str | None] = mapped_column(Text)
    flag_format: Mapped[str | None] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    challenge: Mapped[Challenge] = relationship()


class ChallengeProgress(Base):
    __tablename__ = "challenge_progress"
    __table_args__ = (UniqueConstraint("user_id", "challenge_id", name="uq_progress_user_challenge"),)
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    challenge_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    paused_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    total_paused_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ChallengeSubmission(Timestamped, Base):
    __tablename__ = "challenge_submissions"
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    challenge_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False, index=True)
    submission_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False, server_default=func.now())


class HintUse(Base):
    __tablename__ = "hint_uses"
    __table_args__ = (UniqueConstraint("user_id", "hint_id", name="uq_hint_use_user_hint"),)
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    challenge_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False, index=True)
    hint_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("hints.id", ondelete="CASCADE"), nullable=False)
    cost: Mapped[int] = mapped_column(Integer, nullable=False)
    used_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False, server_default=func.now())


class XpTransaction(Base):
    __tablename__ = "xp_transactions"
    __table_args__ = (UniqueConstraint("user_id", "source_type", "source_id", name="uq_xp_user_source"),)
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("ctf_events.id", ondelete="CASCADE"), nullable=False, index=True)
    challenge_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(24), nullable=False)
    source_id: Mapped[int] = mapped_column(ID_TYPE, nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False, server_default=func.now())


class GradeScale(Timestamped, Base):
    __tablename__ = "grade_scales"
    __table_args__ = (UniqueConstraint("name", "min_score", name="uq_grade_scale_threshold"),)
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    min_score: Mapped[int] = mapped_column(Integer, nullable=False)
    grade_value: Mapped[float] = mapped_column(Float, nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ScoreboardFreeze(Base):
    __tablename__ = "scoreboard_freezes"
    scope: Mapped[str] = mapped_column(String(16), primary_key=True)
    scope_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    snapshot: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    frozen_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False, server_default=func.now())


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False, server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))


class Announcement(Timestamped, Base):
    __tablename__ = "announcements"
    __table_args__ = (CheckConstraint("(class_id IS NULL AND event_id IS NOT NULL) OR (class_id IS NOT NULL AND event_id IS NULL)", name="ck_announcement_exactly_one_scope"),)
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    author_user_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id: Mapped[int | None] = mapped_column(ID_TYPE, ForeignKey("classes.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[int | None] = mapped_column(ID_TYPE, ForeignKey("ctf_events.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    publish_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False, index=True, server_default=func.now())
    archived_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), index=True)
class ChallengeFile(Timestamped, Base):
    __tablename__ = "challenge_files"
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    challenge_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False, index=True)
    original_name: Mapped[str] = mapped_column(String(180), nullable=False)
    storage_name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    challenge: Mapped[Challenge] = relationship(back_populates="files")


class Hint(Timestamped, Base):
    __tablename__ = "hints"
    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    challenge_id: Mapped[int] = mapped_column(ID_TYPE, ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False, index=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    challenge: Mapped[Challenge] = relationship(back_populates="hints")
