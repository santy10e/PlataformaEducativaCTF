"""Persist CTF domain notifications for the student experience."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "a834d227c7b1"
down_revision = "f6a21bc03d5e"
branch_labels = None
depends_on = None

id_type = sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql").with_variant(sa.Integer(), "sqlite")
dt_type = mysql.DATETIME(fsp=6)


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column("user_id", id_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", dt_type, nullable=False, server_default=sa.func.now()),
        sa.Column("read_at", dt_type),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")