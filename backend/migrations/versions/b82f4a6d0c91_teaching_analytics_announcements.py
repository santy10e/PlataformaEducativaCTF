"""Add scoped teacher announcements."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "b82f4a6d0c91"
down_revision = "a834d227c7b1"
branch_labels = None
depends_on = None

id_type = sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql").with_variant(sa.Integer(), "sqlite")
dt_type = mysql.DATETIME(fsp=6)


def upgrade() -> None:
    op.create_table(
        "announcements",
        sa.CheckConstraint("(class_id IS NULL AND event_id IS NOT NULL) OR (class_id IS NOT NULL AND event_id IS NULL)", name="ck_announcement_exactly_one_scope"),
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column("author_user_id", id_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("class_id", id_type, sa.ForeignKey("classes.id", ondelete="CASCADE")),
        sa.Column("event_id", id_type, sa.ForeignKey("ctf_events.id", ondelete="CASCADE")),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("publish_at", dt_type, nullable=False, server_default=sa.func.now()),
        sa.Column("archived_at", dt_type),
        sa.Column("created_at", dt_type, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", dt_type, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_announcements_author_user_id", "announcements", ["author_user_id"])
    op.create_index("ix_announcements_class_id", "announcements", ["class_id"])
    op.create_index("ix_announcements_event_id", "announcements", ["event_id"])
    op.create_index("ix_announcements_publish_at", "announcements", ["publish_at"])
    op.create_index("ix_announcements_archived_at", "announcements", ["archived_at"])


def downgrade() -> None:
    op.drop_table("announcements")
