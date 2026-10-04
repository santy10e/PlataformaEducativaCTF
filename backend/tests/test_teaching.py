from csv import DictReader
from datetime import UTC, datetime, timedelta
from io import StringIO

import pytest
from fastapi import HTTPException
from sqlalchemy import insert, select
from sqlalchemy.orm import Session as DbSession

from app.models import (
    Category,
    Challenge,
    ChallengeProgress,
    ChallengeSubmission,
    CtfEvent,
    Difficulty,
    GradeScale,
    Role,
    SchoolClass,
    User,
)
from app.teaching_api import export
from app.teaching_service import analytics, student_detail


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


def test_event_scope_only_exposes_students_in_instructors_owned_classes(db: DbSession) -> None:
    instructor = make_user(db, "scoped_teacher", "INSTRUCTOR")
    other_teacher = make_user(db, "other_teacher", "INSTRUCTOR")
    own_student = make_user(db, "own_student", "STUDENT")
    other_student = make_user(db, "other_student", "STUDENT")
    own_class = SchoolClass(name="Group A", teacher_user_id=instructor.id, students=[own_student])
    other_class = SchoolClass(name="Group B", teacher_user_id=other_teacher.id, students=[other_student])
    event = CtfEvent(public_id="event-shared-123", name="Shared exercise", mode="JEOPARDY", status="ACTIVE",
                     visibility="ASSIGNED", rules_markdown="", classes=[own_class, other_class])
    db.add(event)
    db.flush()

    report = analytics(db, instructor, class_id=None, event_id=event.id)

    assert [row["display_name"] for row in report["students"]] == ["Own_Student"]
    with pytest.raises(HTTPException) as error:
        student_detail(db, instructor, student_id=other_student.id, class_id=None, event_id=event.id)
    assert error.value.status_code == 404


def test_csv_export_preserves_accents_and_commas_and_includes_grade(db: DbSession) -> None:
    instructor = make_user(db, "export_teacher", "INSTRUCTOR")
    student = make_user(db, "export_student", "STUDENT")
    student.display_name = "Niño, Ana"
    school_class = SchoolClass(name="Aula 1", teacher_user_id=instructor.id, students=[student])
    db.add_all([school_class, GradeScale(name="Secundaria", min_score=0, grade_value=0.0, label="Inicial")])
    db.flush()

    result = export(class_id=school_class.id, actor=instructor, db=db, format="csv")
    csv_text = result.body.decode("utf-8-sig")

    assert "display_name" in csv_text and "grade" in csv_text
    assert '"Niño, Ana"' in csv_text
    assert "0.0" in csv_text


def test_csv_export_treats_untrusted_names_as_text(db: DbSession) -> None:
    instructor = make_user(db, "formula_teacher", "INSTRUCTOR")
    student = make_user(db, "formula_student", "STUDENT")
    student.display_name = ' =HYPERLINK("https://example.invalid","open")'
    school_class = SchoolClass(name="Formula test", teacher_user_id=instructor.id, students=[student])
    db.add(school_class)
    db.flush()

    result = export(class_id=school_class.id, actor=instructor, db=db, format="csv")
    rows = list(DictReader(StringIO(result.body.decode("utf-8-sig"))))

    assert rows[0]["display_name"] == "' =HYPERLINK(\"https://example.invalid\",\"open\")"


def test_analytics_aggregates_synthetic_class_of_500_and_50k_submissions(db: DbSession) -> None:
    instructor = make_user(db, "scale_teacher", "INSTRUCTOR")
    role_user = make_user(db, "student_role_seed", "STUDENT")
    role = role_user.roles[0]
    students = [User(username=f"scale_student_{index}", password_hash="unused", display_name=f"Student {index:03}", is_active=True, roles=[role]) for index in range(500)]
    school_class = SchoolClass(name="Scale test", teacher_user_id=instructor.id, students=students)
    event = CtfEvent(public_id="synthetic-500-50k", name="Synthetic scale test", mode="JEOPARDY", status="ACTIVE",
                     visibility="ASSIGNED", rules_markdown="", classes=[school_class])
    category = Category(name="Synthetic category")
    difficulty = Difficulty(name="Synthetic difficulty")
    db.add_all([event, category, difficulty])
    db.flush()
    challenge = Challenge(public_id="synthetic-challenge", event_id=event.id, category_id=category.id,
        difficulty_id=difficulty.id, slug="synthetic", title="Synthetic challenge", status="PUBLISHED", points=100)
    db.add(challenge)
    db.flush()
    now = datetime.now(UTC).replace(tzinfo=None)
    db.add_all([ChallengeProgress(user_id=student.id, challenge_id=challenge.id, started_at=now - timedelta(hours=1), completed_at=now) for student in students])
    db.flush()
    db.execute(insert(ChallengeSubmission), [
        {"user_id": student.id, "challenge_id": challenge.id, "submission_hash": f"{student.id:08x}{attempt:056x}",
         "is_correct": attempt == 99, "attempted_at": now - timedelta(minutes=99 - attempt)}
        for student in students for attempt in range(100)
    ])
    db.flush()

    report = analytics(db, instructor, class_id=school_class.id, event_id=None)

    assert report["summary"]["students"] == 500
    assert report["summary"]["attempts"] == 50_000
    assert report["summary"]["completed"] == 500
    assert report["summary"]["failed_attempts"] == 49_500
