from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.ctf_service import (
    save_challenge,
    save_event,
    save_taxonomy,
    student_challenges,
    student_events,
)
from app.dependencies import current_session, get_db
from app.main import app
from app.models import Category, CtfEvent, Difficulty, Permission, Role, SchoolClass, User
from app.models import Session as AuthSession
from app.security import digest_token


def _user(db: DbSession, username: str, role_name: str) -> User:
    role = db.scalar(select(Role).where(Role.name == role_name))
    if role is None:
        role = Role(name=role_name, is_system=True)
        db.add(role)
        db.flush()
    user = User(username=username, password_hash="unused", display_name=username, roles=[role], is_active=True)
    db.add(user)
    db.flush()
    return user


def _challenge(db: DbSession, event: CtfEvent, category: Category, difficulty: Difficulty, slug: str, prereqs: list[int] | None = None):
    return save_challenge(db, event, None, category_id=category.id, difficulty_id=difficulty.id, slug=slug, title=slug.title(), description_markdown="Prompt", status="PUBLISHED", points=100, sort_order=0, delivery_type="STATIC", delivery_config={"endpoint": "example.invalid"}, module_id=None, flag_hash="opaque-secret-hash", prerequisite_ids=prereqs or [])


def test_challenge_prerequisites_reject_cycles(db: DbSession) -> None:
    admin = _user(db, "ctfadmin", "ADMIN")
    category = save_taxonomy(db, Category, None, name="Web tests", color="#123456", sort_order=0, multiplier=1.0)
    difficulty = save_taxonomy(db, Difficulty, None, name="Level tests", color="#654321", sort_order=0, multiplier=1.0)
    event = save_event(db, admin, None, name="Cycle test", status="DRAFT", visibility="ASSIGNED", mode="JEOPARDY", rules_markdown="", starts_at=None, ends_at=None, class_ids=[])
    first = _challenge(db, event, category, difficulty, "first")
    second = _challenge(db, event, category, difficulty, "second", [first.id])
    db.flush()
    with pytest.raises(ValueError, match="cycles"):
        save_challenge(db, event, first.id, category_id=category.id, difficulty_id=difficulty.id, slug="first", title="First", description_markdown="", status="DRAFT", points=100, sort_order=0, delivery_type="STATIC", delivery_config={}, module_id=None, flag_hash=None, prerequisite_ids=[second.id])


def test_student_visibility_scopes_event_and_does_not_expose_sensitive_fields(db: DbSession) -> None:
    admin = _user(db, "eventadmin", "ADMIN")
    student = _user(db, "eventlearner", "STUDENT")
    other_student = _user(db, "outsider", "STUDENT")
    school_class = SchoolClass(name="10C", students=[student])
    db.add(school_class)
    db.flush()
    now = datetime.now(UTC)
    event = save_event(db, admin, None, name="Active test", status="PUBLISHED", visibility="ASSIGNED", mode="JEOPARDY", rules_markdown="Read carefully", starts_at=now - timedelta(minutes=1), ends_at=now + timedelta(hours=1), class_ids=[school_class.id])
    category = save_taxonomy(db, Category, None, name="Privacy", color="#123456", sort_order=0, multiplier=1.0)
    difficulty = save_taxonomy(db, Difficulty, None, name="Safe", color="#654321", sort_order=0, multiplier=1.0)
    challenge = _challenge(db, event, category, difficulty, "safe-challenge")
    locked = _challenge(db, event, category, difficulty, "locked-challenge", [challenge.id])
    db.flush()
    visible = student_challenges(db, student, event.public_id)
    assert [item.id for item in visible] == [challenge.id]
    assert [item.id for item in student_challenges(db, student, event.public_id, {challenge.id})] == [challenge.id, locked.id]
    assert student_challenges(db, other_student, event.public_id) == []
    assert not student_challenges(db, student, "unknown-public-id")
    role = student.roles[0]
    role.permissions = [Permission(code="challenge.view", description="View published challenges")]
    app.dependency_overrides[current_session] = lambda: (student, object())
    app.dependency_overrides[get_db] = lambda: db
    try:
        response = TestClient(app).get(f"/api/v1/ctf/student/events/{event.public_id}/challenges")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    item = response.json()[0]
    assert item["public_id"] == challenge.public_id
    assert "flag_hash" not in item
    assert "delivery_config" not in item
    assert "hints" not in item
    assert item["hint_options"] == []
    blocked = next(row for row in response.json() if row["public_id"] == locked.public_id)
    assert blocked["locked"] is True
    assert blocked["lock_reason"] == "Resuelve primero: Safe-Challenge"
    assert blocked["description_markdown"] == ""
    assert blocked["files"] == [] and blocked["hint_options"] == []


def test_instructor_can_only_assign_their_own_classes(db: DbSession) -> None:
    teacher = _user(db, "scope_teacher", "INSTRUCTOR")
    other_teacher = _user(db, "scope_other", "INSTRUCTOR")
    other_class = SchoolClass(name="Other teacher class", teacher_user_id=other_teacher.id)
    db.add(other_class)
    db.flush()
    with pytest.raises(PermissionError, match="classes you teach"):
        save_event(db, teacher, None, name="Unauthorized", status="DRAFT", visibility="ASSIGNED", mode="JEOPARDY", rules_markdown="", starts_at=None, ends_at=None, class_ids=[other_class.id])


def test_challenge_file_upload_sniffs_content_sanitizes_names_and_downloads_authenticated(db: DbSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    actor = _user(db, "file_admin", "ADMIN")
    actor.roles[0].permissions = [Permission(code="challenge.update", description="Edit challenges")]
    category = save_taxonomy(db, Category, None, name="Files", color="#123456", sort_order=0, multiplier=1.0)
    difficulty = save_taxonomy(db, Difficulty, None, name="Simple", color="#654321", sort_order=0, multiplier=1.0)
    event = save_event(db, actor, None, name="Files test", status="DRAFT", visibility="ASSIGNED", mode="JEOPARDY", rules_markdown="", starts_at=None, ends_at=None, class_ids=[])
    challenge = _challenge(db, event, category, difficulty, "file-task")
    db.flush()
    token = "csrf-token"
    session = AuthSession(user_id=actor.id, token_hash=digest_token("opaque-session"), csrf_hash=digest_token(token), csrf_token=token, expires_at=datetime(2099, 1, 1, tzinfo=UTC))
    app.dependency_overrides[current_session] = lambda: (actor, session)
    app.dependency_overrides[get_db] = lambda: db
    monkeypatch.setenv("CHALLENGE_FILE_STORAGE", str(tmp_path))
    try:
        client = TestClient(app)
        upload = client.post(f"/api/v1/ctf/events/{event.id}/challenges/{challenge.id}/files", content=b"%PDF-1.7 test", headers={"x-csrf-token": token, "x-file-name": "../../lesson.pdf", "content-type": "application/octet-stream"})
        assert upload.status_code == 200
        file_data = upload.json()
        assert file_data["name"] == "lesson.pdf"
        assert file_data["content_type"] == "application/pdf"
        assert len(list(tmp_path.iterdir())) == 1
        downloaded = client.get(f"/api/v1/ctf/files/{file_data['public_id']}")
        assert downloaded.status_code == 200
        assert downloaded.content == b"%PDF-1.7 test"
    finally:
        app.dependency_overrides.clear()


def test_duplicate_challenge_starts_as_draft_and_copies_hints(db: DbSession) -> None:
    from app.ctf_service import create_hint, duplicate_challenge

    admin = _user(db, "duplicate_admin", "ADMIN")
    category = save_taxonomy(db, Category, None, name="Duplicate", color="#123456", sort_order=0, multiplier=1.0)
    difficulty = save_taxonomy(db, Difficulty, None, name="Copy", color="#654321", sort_order=0, multiplier=1.0)
    event = save_event(db, admin, None, name="Duplicate test", status="DRAFT", visibility="ASSIGNED", mode="JEOPARDY", rules_markdown="", starts_at=None, ends_at=None, class_ids=[])
    original = _challenge(db, event, category, difficulty, "original")
    create_hint(db, original, order=1, cost=5, content_markdown="Think about the encoding.")
    clone = duplicate_challenge(db, event, original)
    assert clone.id != original.id
    assert clone.slug.startswith("original-copy-")
    assert clone.status == "DRAFT"
    assert clone.flag_hash == original.flag_hash
    assert clone.hints[0].content_markdown == "Think about the encoding."
def test_published_events_allow_open_ended_dates(db: DbSession) -> None:
    admin = _user(db, "open_event_admin", "ADMIN")
    student = _user(db, "open_event_student", "STUDENT")
    school_class = SchoolClass(name="Open event class", students=[student])
    db.add(school_class)
    db.flush()

    event = save_event(db, admin, None, name="Open practice", status="PUBLISHED", visibility="ASSIGNED", mode="JEOPARDY", rules_markdown="", starts_at=None, ends_at=None, class_ids=[school_class.id])

    assert event.status == "PUBLISHED"
    assert event.starts_at is None and event.ends_at is None
    assert [visible.id for visible in student_events(db, student)] == [event.id]
