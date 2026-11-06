"""Composite index for per-learner attempt counts and progress lookups."""

from alembic import op

revision = "c7e1f0a9b3d2"
down_revision = "b82f4a6d0c91"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_challenge_submissions_user_challenge", "challenge_submissions", ["user_id", "challenge_id"])


def downgrade() -> None:
    op.drop_index("ix_challenge_submissions_user_challenge", table_name="challenge_submissions")
