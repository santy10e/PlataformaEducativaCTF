from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.imports_service import confirm_import, preview_csv
from app.models import Role, SchoolClass, Session, User
from app.security import digest_token
from app.users_service import create_user, deactivate_user, get_visible_user, list_users


def make_user(db: DbSession, username: str, role_name: str) -> User:
    role = db.scalar(select(Role).where(Role.name == role_name))
    if role is None:
        role = Role(name=role_name, is_system=True)
        db.add(role)
        db.flush()
    user = User(username=username, password_hash="unused", display_name=username.title(), is_active=True, roles=[role])
    db.add(user)
    db.flush()
    return user


def test_instructor_scope_and_admin_role_protection(db: DbSession) -> None:
    instructor = make_user(db, "teacher", "INSTRUCTOR")
    student_role = make_user(db, "student_seed", "STUDENT")
    school_class = SchoolClass(name="10A", teacher_user_id=instructor.id, students=[student_role])
    db.add(school_class)
    db.flush()

    created = create_user(
        db,
        instructor,
        username="new_student",
        password="temporary-pass-123",
        first_name="Ana",
        last_name="Niño",
        role_name="STUDENT",
        email=None,
        class_ids=[school_class.id],
    )
    assert created.must_change_password is True
    assert created.student_profile is not None
    assert get_visible_user(db, instructor, created.id) is created
    assert list_users(db, instructor, 1, 25, None, "STUDENT")["total"] == 2

    with pytest.raises(PermissionError, match="instructors may only create students"):
        create_user(
            db,
            instructor,
            username="new_admin",
            password="temporary-pass-123",
            first_name="Not",
            last_name="Admin",
            role_name="ADMIN",
            email=None,
            class_ids=[],
        )

    session = Session(user_id=created.id, token_hash=digest_token("session"), csrf_hash=digest_token("csrf"), csrf_token="csrf", expires_at=datetime(2099, 1, 1, tzinfo=UTC))
    db.add(session)
    db.flush()
    deactivate_user(db, created)
    assert created.is_active is False
    assert session.revoked_at is not None


def test_csv_preview_checks_rows_and_confirm_imports_without_plaintext(db: DbSession) -> None:
    actor = make_user(db, "importer", "ADMIN")
    make_user(db, "existing", "STUDENT")
    csv_text = (
        "\ufeffusername,nombre,apellido,curso,email,password_temporal\n"
        "ana01,Ana,Niño,10A,ana@example.edu,Temporary-Password-01\n"
        "ana01,Otra,Persona,10A,otra@example.edu,Temporary-Password-02\n"
        "maria,Maria,Pérez,10B,no-es-email,Temporary-Password-03\n"
        "existing,Cuenta,Duplicada,10A,,Temporary-Password-04\n"
    )
    job, items = preview_csv(db, actor.id, "alumnos.csv", csv_text)
    assert job.row_count == 4
    assert job.valid_count == 1
    assert job.error_count == 3
    assert items[0]["first_name"] == "Ana"
    assert "password_hash" not in items[0]
    assert "Temporary-Password-01" not in str(job.preview_rows)
    assert job.preview_rows[0].get("password_hash")

    result = confirm_import(db, job)
    assert result["imported_count"] == 1
    assert result["class_count"] == 1
    imported = db.scalar(select(User).where(User.username == "ana01"))
    assert imported is not None
    assert imported.must_change_password is True
    assert imported.student_profile is not None
    assert imported.student_profile.last_name == "Niño"
    assert imported.enrolled_classes[0].name == "10A"
    assert "password_hash" not in str(job.preview_rows)
    assert confirm_import(db, job)["already_imported"] is True


def test_csv_import_rejects_oversized_content_and_row_count(db: DbSession) -> None:
    with pytest.raises(ValueError, match="2 MB"):
        preview_csv(db, 1, "large.csv", "x" * 2_000_001)
    rows = "username,nombre,apellido,curso,password_temporal\n" + "\n".join([",,,," for _ in range(501)])
    with pytest.raises(ValueError, match="500 row limit"):
        preview_csv(db, 1, "too-many.csv", rows)


def test_instructor_membership_is_limited_to_owned_classes(db: DbSession) -> None:
    first = make_user(db, "teacher1", "INSTRUCTOR")
    second = make_user(db, "teacher2", "INSTRUCTOR")
    student = make_user(db, "learner", "STUDENT")
    db.add_all([SchoolClass(name="10A", teacher_user_id=first.id, students=[student]), SchoolClass(name="10B", teacher_user_id=second.id)])
    db.flush()
    assert get_visible_user(db, first, student.id) is student
    assert get_visible_user(db, second, student.id) is None

