"""Curriculum: courses, modules, lessons, activities, hints and activity progress (SPEC phase 4)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "d9f3a2c6e1b4"
down_revision = "c7e1f0a9b3d2"
branch_labels = None
depends_on = None

id_type = sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql").with_variant(sa.Integer(), "sqlite")
dt = mysql.DATETIME(fsp=6)


def _timestamps() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column("created_at", dt, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", dt, nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    op.create_table(
        "courses",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description_markdown", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("owner_user_id", id_type, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("deleted_at", dt),
        *_timestamps(),
    )
    op.create_index("ix_courses_public_id", "courses", ["public_id"], unique=True)
    op.create_index("ix_courses_status", "courses", ["status"])
    op.create_index("ix_courses_owner_user_id", "courses", ["owner_user_id"])
    op.create_index("ix_courses_deleted_at", "courses", ["deleted_at"])

    op.create_table(
        "course_classes",
        sa.Column("course_id", id_type, sa.ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("class_id", id_type, sa.ForeignKey("classes.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "modules",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column("course_id", id_type, sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description_markdown", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("deleted_at", dt),
        *_timestamps(),
    )
    op.create_index("ix_modules_public_id", "modules", ["public_id"], unique=True)
    op.create_index("ix_modules_course_id", "modules", ["course_id"])
    op.create_index("ix_modules_deleted_at", "modules", ["deleted_at"])

    op.create_table(
        "lessons",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column("module_id", id_type, sa.ForeignKey("modules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("estimated_minutes", sa.Integer()),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("deleted_at", dt),
        *_timestamps(),
    )
    op.create_index("ix_lessons_public_id", "lessons", ["public_id"], unique=True)
    op.create_index("ix_lessons_module_id", "lessons", ["module_id"])
    op.create_index("ix_lessons_deleted_at", "lessons", ["deleted_at"])

    op.create_table(
        "activities",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column("lesson_id", id_type, sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(40), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("description_markdown", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("category_id", id_type, sa.ForeignKey("categories.id", ondelete="RESTRICT")),
        sa.Column("difficulty_id", id_type, sa.ForeignKey("difficulties.id", ondelete="RESTRICT")),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("xp", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("deleted_at", dt),
        *_timestamps(),
    )
    op.create_index("ix_activities_public_id", "activities", ["public_id"], unique=True)
    for column in ("lesson_id", "type", "category_id", "difficulty_id", "status", "deleted_at"):
        op.create_index(f"ix_activities_{column}", "activities", [column])

    op.create_table(
        "activity_prerequisites",
        sa.Column("activity_id", id_type, sa.ForeignKey("activities.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("required_activity_id", id_type, sa.ForeignKey("activities.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "activity_hints",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column("activity_id", id_type, sa.ForeignKey("activities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("cost", sa.Integer(), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("activity_id", "order", name="uq_activity_hint_order"),
    )
    op.create_index("ix_activity_hints_activity_id", "activity_hints", ["activity_id"])

    op.create_table(
        "hint_usage",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column("user_id", id_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("activity_id", id_type, sa.ForeignKey("activities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hint_id", id_type, sa.ForeignKey("activity_hints.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cost", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("user_id", "hint_id", name="uq_hint_usage_user_hint"),
    )
    op.create_index("ix_hint_usage_user_id", "hint_usage", ["user_id"])
    op.create_index("ix_hint_usage_activity_id", "hint_usage", ["activity_id"])

    op.create_table(
        "activity_progress",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column("user_id", id_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("activity_id", id_type, sa.ForeignKey("activities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", dt),
        sa.Column("submitted_at", dt),
        sa.Column("completed_at", dt),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer()),
        sa.Column("max_score", sa.Integer()),
        sa.Column("submission", sa.JSON(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("reviewed_by_user_id", id_type, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reviewed_at", dt),
        sa.Column("auto_graded", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("user_id", "activity_id", name="uq_activity_progress_user_activity"),
    )
    op.create_index("ix_activity_progress_user_id", "activity_progress", ["user_id"])
    op.create_index("ix_activity_progress_activity_id", "activity_progress", ["activity_id"])
    # Review queue reads by status in submission order (SPEC §9: index the review queue).
    op.create_index("ix_activity_progress_status_submitted", "activity_progress", ["status", "submitted_at"])


def downgrade() -> None:
    for table in ("activity_progress", "hint_usage", "activity_hints", "activity_prerequisites", "activities", "lessons", "modules", "course_classes", "courses"):
        op.drop_table(table)
