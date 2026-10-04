"""Add education profiles, classes and CSV import jobs."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "c1a6d7e94b32"
down_revision = "e2b4a4f39788"
branch_labels = None
depends_on = None

id_type = sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql").with_variant(sa.Integer(), "sqlite")
timestamp_type = mysql.DATETIME(fsp=6)


def upgrade() -> None:
    op.add_column("users", sa.Column("email", sa.String(254), nullable=True))
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.add_column("users", sa.Column("must_change_password", sa.Boolean(), server_default=sa.false(), nullable=False))

    op.create_table(
        "student_profiles",
        sa.Column("user_id", id_type, nullable=False),
        sa.Column("first_name", sa.String(80), nullable=False),
        sa.Column("last_name", sa.String(80), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "teacher_profiles",
        sa.Column("user_id", id_type, nullable=False),
        sa.Column("first_name", sa.String(80), nullable=False),
        sa.Column("last_name", sa.String(80), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "classes",
        sa.Column("id", id_type, autoincrement=True, nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("academic_period", sa.String(32), nullable=False, server_default=""),
        sa.Column("description", sa.String(255), nullable=False, server_default=""),
        sa.Column("teacher_user_id", id_type, nullable=True),
        sa.Column("created_at", timestamp_type, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", timestamp_type, nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["teacher_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_classes_name", "classes", ["name"])
    op.create_index("ix_classes_teacher_user_id", "classes", ["teacher_user_id"])
    op.create_table(
        "class_students",
        sa.Column("class_id", id_type, nullable=False),
        sa.Column("student_user_id", id_type, nullable=False),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("class_id", "student_user_id"),
    )
    op.create_index("ix_class_students_student_user_id", "class_students", ["student_user_id"])
    op.create_table(
        "import_jobs",
        sa.Column("id", id_type, autoincrement=True, nullable=False),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column("actor_user_id", id_type, nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="PREVIEWED"),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("preview_rows", sa.JSON(), nullable=False),
        sa.Column("created_at", timestamp_type, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", timestamp_type, nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
    )
    op.create_index("ix_import_jobs_public_id", "import_jobs", ["public_id"])
    op.create_index("ix_import_jobs_actor_user_id", "import_jobs", ["actor_user_id"])


def downgrade() -> None:
    op.drop_index("ix_import_jobs_actor_user_id", table_name="import_jobs")
    op.drop_index("ix_import_jobs_public_id", table_name="import_jobs")
    op.drop_table("import_jobs")
    op.drop_index("ix_class_students_student_user_id", table_name="class_students")
    op.drop_table("class_students")
    op.drop_index("ix_classes_teacher_user_id", table_name="classes")
    op.drop_index("ix_classes_name", table_name="classes")
    op.drop_table("classes")
    op.drop_table("teacher_profiles")
    op.drop_table("student_profiles")
    op.drop_column("users", "must_change_password")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_column("users", "email")
