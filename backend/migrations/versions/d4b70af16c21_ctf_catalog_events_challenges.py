"""Add CTF event, category, difficulty, challenge, file and hint tables."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "d4b70af16c21"
down_revision = "c1a6d7e94b32"
branch_labels = None
depends_on = None

id_type = sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql").with_variant(sa.Integer(), "sqlite")
dt_type = mysql.DATETIME(fsp=6)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", dt_type, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", dt_type, nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("categories"):
        op.create_table("categories", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("name", sa.String(80), nullable=False, unique=True), sa.Column("color", sa.String(7), nullable=False, server_default="#587666"), sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"), sa.Column("multiplier", sa.Float(), nullable=False, server_default="1"), *_timestamps())
    if not inspector.has_table("difficulties"):
        op.create_table("difficulties", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("name", sa.String(48), nullable=False, unique=True), sa.Column("color", sa.String(7), nullable=False, server_default="#587666"), sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"), sa.Column("multiplier", sa.Float(), nullable=False, server_default="1"), *_timestamps())
    op.create_table("ctf_events", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("public_id", sa.String(36), nullable=False, unique=True), sa.Column("name", sa.String(160), nullable=False), sa.Column("mode", sa.String(24), nullable=False, server_default="JEOPARDY"), sa.Column("status", sa.String(24), nullable=False, server_default="DRAFT"), sa.Column("visibility", sa.String(24), nullable=False, server_default="ASSIGNED"), sa.Column("rules_markdown", sa.Text(), nullable=False), sa.Column("starts_at", dt_type), sa.Column("ends_at", dt_type), sa.Column("deleted_at", dt_type), *_timestamps())
    op.create_index("ix_ctf_events_public_id", "ctf_events", ["public_id"], unique=True)
    op.create_index("ix_ctf_events_status", "ctf_events", ["status"])
    op.create_index("ix_ctf_events_deleted_at", "ctf_events", ["deleted_at"])
    op.create_table("ctf_event_classes", sa.Column("event_id", id_type, sa.ForeignKey("ctf_events.id", ondelete="CASCADE"), primary_key=True), sa.Column("class_id", id_type, sa.ForeignKey("classes.id", ondelete="CASCADE"), primary_key=True))
    op.create_table("challenges", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("public_id", sa.String(36), nullable=False, unique=True), sa.Column("event_id", id_type, sa.ForeignKey("ctf_events.id", ondelete="CASCADE"), nullable=False), sa.Column("category_id", id_type, sa.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False), sa.Column("difficulty_id", id_type, sa.ForeignKey("difficulties.id", ondelete="RESTRICT"), nullable=False), sa.Column("slug", sa.String(100), nullable=False), sa.Column("title", sa.String(180), nullable=False), sa.Column("description_markdown", sa.Text(), nullable=False), sa.Column("status", sa.String(24), nullable=False, server_default="DRAFT"), sa.Column("points", sa.Integer(), nullable=False, server_default="100"), sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"), sa.Column("delivery_type", sa.String(24), nullable=False, server_default="STATIC"), sa.Column("delivery_config", sa.JSON(), nullable=False), sa.Column("module_id", sa.String(100)), sa.Column("flag_hash", sa.String(255)), sa.Column("deleted_at", dt_type), *_timestamps())
    for column in ("public_id", "event_id", "category_id", "difficulty_id", "status", "deleted_at"):
        op.create_index(f"ix_challenges_{column}", "challenges", [column], unique=column == "public_id")
    op.create_table("challenge_prerequisites", sa.Column("challenge_id", id_type, sa.ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True), sa.Column("prerequisite_id", id_type, sa.ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True))
    op.create_table("challenge_files", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("public_id", sa.String(36), nullable=False, unique=True), sa.Column("challenge_id", id_type, sa.ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False), sa.Column("original_name", sa.String(180), nullable=False), sa.Column("storage_name", sa.String(80), nullable=False, unique=True), sa.Column("content_type", sa.String(120), nullable=False), sa.Column("size_bytes", sa.Integer(), nullable=False), sa.Column("sha256", sa.String(64), nullable=False), *_timestamps())
    op.create_index("ix_challenge_files_public_id", "challenge_files", ["public_id"], unique=True)
    op.create_index("ix_challenge_files_challenge_id", "challenge_files", ["challenge_id"])
    op.create_index("ix_challenge_files_storage_name", "challenge_files", ["storage_name"], unique=True)
    op.create_table("hints", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("challenge_id", id_type, sa.ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False), sa.Column("order", sa.Integer(), nullable=False), sa.Column("cost", sa.Integer(), nullable=False, server_default="0"), sa.Column("content_markdown", sa.Text(), nullable=False), *_timestamps())
    op.create_index("ix_hints_challenge_id", "hints", ["challenge_id"])


def downgrade() -> None:
    op.drop_table("hints")
    for name in ("ix_challenge_files_storage_name", "ix_challenge_files_challenge_id", "ix_challenge_files_public_id"):
        op.drop_index(name, table_name="challenge_files")
    op.drop_table("challenge_files")
    op.drop_table("challenge_prerequisites")
    for name in ("ix_challenges_deleted_at", "ix_challenges_status", "ix_challenges_difficulty_id", "ix_challenges_category_id", "ix_challenges_event_id", "ix_challenges_public_id"):
        op.drop_index(name, table_name="challenges")
    op.drop_table("challenges")
    op.drop_table("ctf_event_classes")
    for name in ("ix_ctf_events_deleted_at", "ix_ctf_events_status", "ix_ctf_events_public_id"):
        op.drop_index(name, table_name="ctf_events")
    op.drop_table("ctf_events")
    op.drop_table("difficulties")
    op.drop_table("categories")
