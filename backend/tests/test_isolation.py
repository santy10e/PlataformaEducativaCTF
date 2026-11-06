"""Cross-teacher isolation: one instructor must never read or change another instructor's data."""

import pytest
from helpers import Caller
from helpers import make_role as _role
from helpers import make_user as _user
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.ctf_service import duplicate_event, save_event
from app.imports_service import confirm_import, preview_csv
from app.models import CtfEvent, SchoolClass, User


def _event_payload(name: str, class_ids: list[int]) -> dict[str, object]:
    return {"name": name, "status": "DRAFT", "visibility": "ASSIGNED", "mode": "JEOPARDY", "class_ids": class_ids}


def _two_teachers(db: DbSession) -> tuple[User, User, SchoolClass, SchoolClass]:
    _role(db, "STUDENT", ("challenge.view",))
    first = _user(db, "teacher_a", "INSTRUCTOR")
    second = _user(db, "teacher_b", "INSTRUCTOR")
    class_a = SchoolClass(name="Class A", academic_period="2026", teacher_user_id=first.id)
    class_b = SchoolClass(name="Class B", academic_period="2026", teacher_user_id=second.id)
    db.add_all([class_a, class_b])
    db.flush()
    return first, second, class_a, class_b


def test_instructor_cannot_modify_another_instructors_event(db: DbSession, call: Caller) -> None:
    first, second, class_a, class_b = _two_teachers(db)
    event = save_event(db, first, None, name="Teacher A event", status="PUBLISHED", visibility="ASSIGNED", mode="JEOPARDY", rules_markdown="", starts_at=None, ends_at=None, class_ids=[class_a.id])
    db.commit()

    response = call(second, "PUT", f"/api/v1/ctf/events/{event.id}", json=_event_payload("taken over", [class_b.id]))
    assert response.status_code == 404
    other = call(second, "PUT", f"/api/v1/ctf/events/{event.id}", json=_event_payload("wiped", []))
    assert other.status_code == 404

    db.refresh(event)
    assert event.name == "Teacher A event"
    assert [item.id for item in event.classes] == [class_a.id]
    assert call(second, "GET", f"/api/v1/ctf/events/{event.id}").status_code == 404
    assert call(first, "GET", f"/api/v1/ctf/events/{event.id}").status_code == 200


def test_instructor_event_must_include_an_owned_class(db: DbSession, call: Caller) -> None:
    first, _second, class_a, _class_b = _two_teachers(db)

    orphan = call(first, "POST", "/api/v1/ctf/events", json=_event_payload("orphan", []))
    assert orphan.status_code == 422
    created = call(first, "POST", "/api/v1/ctf/events", json=_event_payload("with class", [class_a.id]))
    assert created.status_code == 200
    # The event stays reachable after creation: the exact failure that orphaned events caused.
    assert call(first, "GET", f"/api/v1/ctf/events/{created.json()['id']}").status_code == 200


def test_shared_event_keeps_the_other_teachers_classes(db: DbSession, call: Caller) -> None:
    first, second, class_a, class_b = _two_teachers(db)
    admin = _user(db, "root", "ADMIN")
    event = save_event(db, admin, None, name="Shared", status="DRAFT", visibility="ASSIGNED", mode="JEOPARDY", rules_markdown="", starts_at=None, ends_at=None, class_ids=[class_a.id, class_b.id])
    db.commit()

    response = call(first, "PUT", f"/api/v1/ctf/events/{event.id}", json=_event_payload("Shared v2", [class_a.id]))
    assert response.status_code == 200
    db.refresh(event)
    assert {item.id for item in event.classes} == {class_a.id, class_b.id}

    copy = duplicate_event(db, first, event)
    assert [item.id for item in copy.classes] == [class_a.id]
    assert call(second, "GET", f"/api/v1/ctf/events/{event.id}").status_code == 200


def test_instructor_cannot_enroll_students_from_other_classes(db: DbSession, call: Caller) -> None:
    first, second, class_a, class_b = _two_teachers(db)
    own = _user(db, "own_student", "STUDENT")
    foreign = _user(db, "foreign_student", "STUDENT")
    unassigned = _user(db, "unassigned_student", "STUDENT")
    class_a.students = [own]
    class_b.students = [foreign]
    db.commit()

    for stranger in (foreign, unassigned):
        rejected = call(second, "PUT", f"/api/v1/classes/{class_b.id}/students", json={"student_ids": [foreign.id, stranger.id, own.id]})
        assert rejected.status_code == 422
    rejected = call(first, "PUT", f"/api/v1/classes/{class_a.id}/students", json={"student_ids": [own.id, foreign.id]})
    assert rejected.status_code == 422

    db.refresh(class_a)
    assert [student.id for student in class_a.students] == [own.id]
    # Reorganising (here: removing) students already in scope remains allowed.
    assert call(first, "PUT", f"/api/v1/classes/{class_a.id}/students", json={"student_ids": []}).status_code == 200
    # Administrators can enrol anyone.
    admin = _user(db, "root2", "ADMIN")
    assert call(admin, "PUT", f"/api/v1/classes/{class_a.id}/students", json={"student_ids": [foreign.id]}).status_code == 200


CSV_HEADER = "username,nombre,apellido,curso,password_temporal\n"


def test_csv_import_never_joins_another_teachers_class(db: DbSession) -> None:
    first, second, class_a, _class_b = _two_teachers(db)
    class_a.academic_period = ""  # legacy rows with an empty period were the exposed case
    db.flush()
    job, items = preview_csv(db, second.id, "a.csv", CSV_HEADER + "new.one,Ana,Perez,Class A,Temporary-Pass-01\n")
    assert items[0]["valid"] is True
    result = confirm_import(db, job)
    assert result["class_count"] == 1

    imported = db.scalar(select(User).where(User.username == "new.one"))
    assert imported is not None
    assert class_a.id not in [item.id for item in imported.enrolled_classes]
    created = imported.enrolled_classes[0]
    assert created.teacher_user_id == second.id
    db.refresh(class_a)
    assert class_a.students == []
    assert first.id == class_a.teacher_user_id


def test_csv_import_reuses_existing_class_even_with_an_academic_period(db: DbSession) -> None:
    first, _second, class_a, _class_b = _two_teachers(db)
    job, _items = preview_csv(db, first.id, "a.csv", CSV_HEADER + "reuse.one,Ana,Perez,Class A,Temporary-Pass-01\n")
    result = confirm_import(db, job)
    assert result["class_count"] == 0
    assert db.scalars(select(SchoolClass).where(SchoolClass.name == "Class A")).all() == [class_a]
    assert [student.username for student in class_a.students] == ["reuse.one"]


def test_admin_import_creates_unassigned_classes_and_flags_ambiguous_names(db: DbSession) -> None:
    _role(db, "STUDENT", ("challenge.view",))
    admin = _user(db, "importer_admin", "ADMIN")
    job, _ = preview_csv(db, admin.id, "a.csv", CSV_HEADER + "fresh.one,Ana,Perez,Brand New,Temporary-Pass-01\n")
    confirm_import(db, job)
    created = db.scalar(select(SchoolClass).where(SchoolClass.name == "Brand New"))
    assert created is not None and created.teacher_user_id is None

    teacher = _user(db, "dup_teacher", "INSTRUCTOR")
    db.add_all([SchoolClass(name="Twin", teacher_user_id=teacher.id, academic_period="2025"), SchoolClass(name="Twin", teacher_user_id=teacher.id, academic_period="2026")])
    db.flush()
    _job, items = preview_csv(db, admin.id, "a.csv", CSV_HEADER + "twin.one,Ana,Perez,Twin,Temporary-Pass-01\n")
    assert items[0]["valid"] is False
    assert any("several classes" in error for error in items[0]["errors"])  # type: ignore[attr-defined]


def test_event_ownership_is_checked_before_validation_details_leak(db: DbSession) -> None:
    first, second, class_a, _class_b = _two_teachers(db)
    event = save_event(db, first, None, name="Private", status="DRAFT", visibility="ASSIGNED", mode="JEOPARDY", rules_markdown="", starts_at=None, ends_at=None, class_ids=[class_a.id])
    with pytest.raises(LookupError):
        save_event(db, second, event.id, name="x" * 5, status="DRAFT", visibility="ASSIGNED", mode="JEOPARDY", rules_markdown="", starts_at=None, ends_at=None, class_ids=[999999])
    assert db.get(CtfEvent, event.id) is event
