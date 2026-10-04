"""Add flag strategies, challenge progress, score ledger and grade scales."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "f6a21bc03d5e"
down_revision = "d4b70af16c21"
branch_labels = None
depends_on = None

id_type = sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql").with_variant(sa.Integer(), "sqlite")
dt_type = mysql.DATETIME(fsp=6)


def _timestamps() -> list[sa.Column]:
    return [sa.Column("created_at", dt_type, nullable=False, server_default=sa.func.now()), sa.Column("updated_at", dt_type, nullable=False, server_default=sa.func.now())]


def upgrade() -> None:
    op.add_column("ctf_events", sa.Column("scoring_strategy", sa.String(32), nullable=False, server_default="FIXED"))
    op.add_column("ctf_events", sa.Column("scoring_config", sa.JSON(), nullable=True))
    op.add_column("ctf_events", sa.Column("max_attempts", sa.Integer()))
    op.add_column("ctf_events", sa.Column("scoreboard_frozen", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute(sa.text("UPDATE ctf_events SET scoring_config = '{}' WHERE scoring_config IS NULL"))
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("ctf_events", "scoring_config", existing_type=sa.JSON(), nullable=False)
    op.add_column("challenges", sa.Column("scoring_strategy", sa.String(32)))
    op.add_column("challenges", sa.Column("scoring_config", sa.JSON(), nullable=True))
    op.add_column("challenges", sa.Column("max_attempts", sa.Integer()))
    op.execute(sa.text("UPDATE challenges SET scoring_config = '{}' WHERE scoring_config IS NULL"))
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("challenges", "scoring_config", existing_type=sa.JSON(), nullable=False)
    op.create_table("challenge_flags", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("challenge_id", id_type, sa.ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False), sa.Column("strategy", sa.String(24), nullable=False), sa.Column("matcher", sa.Text()), sa.Column("flag_format", sa.String(255)), sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()), *_timestamps())
    op.create_index("ix_challenge_flags_challenge_id", "challenge_flags", ["challenge_id"])
    op.create_table("challenge_progress", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("user_id", id_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("challenge_id", id_type, sa.ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False), sa.Column("started_at", dt_type, nullable=False), sa.Column("completed_at", dt_type), sa.Column("paused_at", dt_type), sa.Column("total_paused_seconds", sa.Integer(), nullable=False, server_default="0"), sa.UniqueConstraint("user_id", "challenge_id", name="uq_progress_user_challenge"))
    op.create_index("ix_challenge_progress_user_id", "challenge_progress", ["user_id"])
    op.create_index("ix_challenge_progress_challenge_id", "challenge_progress", ["challenge_id"])
    op.create_table("challenge_submissions", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("user_id", id_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("challenge_id", id_type, sa.ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False), sa.Column("submission_hash", sa.String(64), nullable=False), sa.Column("is_correct", sa.Boolean(), nullable=False), sa.Column("attempted_at", dt_type, nullable=False, server_default=sa.func.now()), *_timestamps())
    op.create_index("ix_challenge_submissions_user_id", "challenge_submissions", ["user_id"])
    op.create_index("ix_challenge_submissions_challenge_id", "challenge_submissions", ["challenge_id"])
    op.create_table("hint_uses", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("user_id", id_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("challenge_id", id_type, sa.ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False), sa.Column("hint_id", id_type, sa.ForeignKey("hints.id", ondelete="CASCADE"), nullable=False), sa.Column("cost", sa.Integer(), nullable=False), sa.Column("used_at", dt_type, nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("user_id", "hint_id", name="uq_hint_use_user_hint"))
    op.create_index("ix_hint_uses_user_id", "hint_uses", ["user_id"])
    op.create_index("ix_hint_uses_challenge_id", "hint_uses", ["challenge_id"])
    op.create_table("xp_transactions", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("user_id", id_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("event_id", id_type, sa.ForeignKey("ctf_events.id", ondelete="CASCADE"), nullable=False), sa.Column("challenge_id", id_type, sa.ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False), sa.Column("source_type", sa.String(24), nullable=False), sa.Column("source_id", id_type, nullable=False), sa.Column("points", sa.Integer(), nullable=False), sa.Column("created_at", dt_type, nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("user_id", "source_type", "source_id", name="uq_xp_user_source"))
    for column in ("user_id", "event_id", "challenge_id"):
        op.create_index(f"ix_xp_transactions_{column}", "xp_transactions", [column])
    op.create_table("grade_scales", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("name", sa.String(80), nullable=False), sa.Column("min_score", sa.Integer(), nullable=False), sa.Column("grade_value", sa.Float(), nullable=False), sa.Column("label", sa.String(80), nullable=False, server_default=""), sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"), *_timestamps(), sa.UniqueConstraint("name", "min_score", name="uq_grade_scale_threshold"))
    op.create_index("ix_grade_scales_name", "grade_scales", ["name"])
    op.create_table("scoreboard_freezes", sa.Column("scope", sa.String(16), primary_key=True), sa.Column("scope_id", sa.String(64), primary_key=True), sa.Column("snapshot", sa.JSON(), nullable=False), sa.Column("frozen_at", dt_type, nullable=False, server_default=sa.func.now()))


def downgrade() -> None:
    op.drop_table("scoreboard_freezes")
    op.drop_index("ix_grade_scales_name", table_name="grade_scales")
    op.drop_table("grade_scales")
    for column in ("challenge_id", "event_id", "user_id"):
        op.drop_index(f"ix_xp_transactions_{column}", table_name="xp_transactions")
    op.drop_table("xp_transactions")
    for table, columns in (("hint_uses", ("challenge_id", "user_id")), ("challenge_submissions", ("challenge_id", "user_id")), ("challenge_progress", ("challenge_id", "user_id"))):
        for column in columns:
            op.drop_index(f"ix_{table}_{column}", table_name=table)
        op.drop_table(table)
    op.drop_index("ix_challenge_flags_challenge_id", table_name="challenge_flags")
    op.drop_table("challenge_flags")
    for column in ("scoring_config", "scoring_strategy", "max_attempts"):
        op.drop_column("challenges", column)
    for column in ("scoreboard_frozen", "max_attempts", "scoring_config", "scoring_strategy"):
        op.drop_column("ctf_events", column)