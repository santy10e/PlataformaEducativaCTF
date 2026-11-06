"""Authentication, error-envelope, admin-safety and publication rules found by the audit."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from helpers import Caller, make_role, make_user
from sqlalchemy.orm import Session as DbSession

from app.ctf_service import save_event, save_taxonomy
from app.main import app
from app.models import Category, Difficulty, SchoolClass
from app.models import Session as AuthSession
from app.security import LoginRateLimiter, digest_token, hash_password, login_limiter
from app.users_service import ensure_can_deactivate


@pytest.fixture(autouse=True)
def clean_limiter() -> Generator[None, None, None]:
    login_limiter.attempts.clear()
    yield
    login_limiter.attempts.clear()


def test_temporary_password_only_unlocks_the_password_change(db: DbSession, call: Caller) -> None:
    student = make_user(db, "temp_student", "INSTRUCTOR")
    student.password_hash = hash_password("Temporary-Pass-2026")
    student.must_change_password = True
    db.flush()

    blocked = call(student, "GET", "/api/v1/classes")
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "PASSWORD_CHANGE_REQUIRED"
    assert call(student, "GET", "/api/v1/auth/me").status_code == 200

    changed = call(student, "POST", "/api/v1/auth/change-password", json={"current_password": "Temporary-Pass-2026", "new_password": "Brand-New-Password-1"})
    assert changed.status_code == 200
    assert call(student, "GET", "/api/v1/classes").status_code == 200


def test_changing_the_password_signs_out_every_other_session(db: DbSession, call: Caller) -> None:
    user = make_user(db, "rotating", "INSTRUCTOR")
    user.password_hash = hash_password("Current-Password-2026")
    stolen = AuthSession(user_id=user.id, token_hash=digest_token("stolen"), csrf_hash=digest_token("c"), csrf_token="c", expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1))
    db.add(stolen)
    db.flush()

    response = call(user, "POST", "/api/v1/auth/change-password", json={"current_password": "Current-Password-2026", "new_password": "Another-Password-2026"})
    assert response.status_code == 200
    assert stolen.revoked_at is not None
    assert call.session_for(user).revoked_at is None


def test_successful_logins_do_not_consume_the_limiter(db: DbSession, call: Caller) -> None:
    user = make_user(db, "busy_learner", "INSTRUCTOR")
    user.password_hash = hash_password("Correct-Password-2026")
    db.flush()
    from app.dependencies import get_db

    app.dependency_overrides[get_db] = lambda: db
    for _ in range(12):
        ok = call.client.post("/api/v1/auth/login", json={"username": "busy_learner", "password": "Correct-Password-2026"})
        assert ok.status_code == 200
    for _ in range(8):
        assert call.client.post("/api/v1/auth/login", json={"username": "busy_learner", "password": "wrong-password-xx"}).status_code == 401
    assert call.client.post("/api/v1/auth/login", json={"username": "busy_learner", "password": "wrong-password-xx"}).status_code == 429
    # A success afterwards is also refused while locked (that client), proving lockout works...
    assert call.client.post("/api/v1/auth/login", json={"username": "busy_learner", "password": "Correct-Password-2026"}).status_code == 429


def test_limiter_blocks_per_client_not_per_account() -> None:
    limiter = LoginRateLimiter(limit=3, window_seconds=300, ip_limit=50)
    attacker = ("ipuser:10.0.0.9|victim", "ip:10.0.0.9")
    teacher = ("ipuser:10.0.0.5|victim", "ip:10.0.0.5")
    for _ in range(3):
        limiter.allow(*attacker, now=0)
    assert limiter.blocked(*attacker, now=1)
    assert not limiter.blocked(*teacher, now=1)
    limiter.reset(attacker[0])
    assert not limiter.blocked(attacker[0], now=1)
    assert not limiter.blocked(*attacker, now=1000)  # allowance returns after the window


def test_every_error_uses_the_contract_envelope(db: DbSession) -> None:
    router = APIRouter()

    @router.get("/api/v1/_boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    app.include_router(router)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        missing = client.get("/api/v1/does-not-exist")
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
        wrong_method = client.delete("/api/v1/health")
        assert wrong_method.status_code == 405
        assert wrong_method.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
        crashed = client.get("/api/v1/_boom")
        assert crashed.status_code == 500
        assert crashed.json() == {"error": {"code": "INTERNAL_ERROR", "message": "unexpected server error", "details": {}}}
    finally:
        app.router.routes[:] = [route for route in app.router.routes if getattr(route, "path", "") != "/api/v1/_boom"]


def test_administrators_cannot_lock_the_platform_out(db: DbSession, call: Caller) -> None:
    sole = make_user(db, "only_admin", "ADMIN")
    helper = make_user(db, "helper_admin", "ADMIN")
    with pytest.raises(ValueError, match="own account"):
        ensure_can_deactivate(db, sole, sole)

    own = call(sole, "PATCH", f"/api/v1/users/{sole.id}/status", json={"is_active": False})
    assert own.status_code == 409 and sole.is_active is True
    # Two admins: one may deactivate the other, but never the last one standing.
    assert call(sole, "PATCH", f"/api/v1/users/{helper.id}/status", json={"is_active": False}).status_code == 200
    with pytest.raises(ValueError, match="last active administrator"):
        ensure_can_deactivate(db, sole, helper)


def test_administrator_role_permissions_are_protected(db: DbSession, call: Caller) -> None:
    admin = make_user(db, "role_admin", "ADMIN")
    role = admin.roles[0]
    response = call(admin, "PUT", f"/api/v1/admin/roles/{role.id}", json={"name": "ADMIN", "permissions": []})
    assert response.status_code == 403
    assert role.permissions


def test_only_administrators_create_instructor_accounts(db: DbSession, call: Caller) -> None:
    teacher = make_user(db, "recruiter", "INSTRUCTOR")
    make_role(db, "INSTRUCTOR", ())
    payload = {"username": "colleague", "password": "Temporary-Pass-2026", "first_name": "Col", "last_name": "League", "role": "INSTRUCTOR"}
    assert call(teacher, "POST", "/api/v1/users", json=payload).status_code == 403
    admin = make_user(db, "boss", "ADMIN")
    assert call(admin, "POST", "/api/v1/users", json=payload).status_code == 200


def test_a_challenge_cannot_be_published_without_a_flag(db: DbSession, call: Caller) -> None:
    teacher = make_user(db, "author", "INSTRUCTOR")
    school_class = SchoolClass(name="Authors", teacher_user_id=teacher.id)
    db.add(school_class)
    db.flush()
    event = save_event(db, teacher, None, name="Flags needed", status="DRAFT", visibility="ASSIGNED", mode="JEOPARDY", rules_markdown="", starts_at=None, ends_at=None, class_ids=[school_class.id])
    category = save_taxonomy(db, Category, None, name="Misc", color="#123456", sort_order=0, multiplier=1.0)
    difficulty = save_taxonomy(db, Difficulty, None, name="Easy", color="#654321", sort_order=0, multiplier=1.0)
    db.commit()
    body = {"category_id": category.id, "difficulty_id": difficulty.id, "slug": "needs-flag", "title": "Needs flag", "status": "DRAFT"}
    base = f"/api/v1/ctf/events/{event.id}/challenges"

    assert call(teacher, "POST", base, json={**body, "status": "PUBLISHED"}).status_code == 422
    created = call(teacher, "POST", base, json=body)
    assert created.status_code == 200
    challenge_id = created.json()["id"]
    assert call(teacher, "PUT", f"{base}/{challenge_id}", json={**body, "status": "PUBLISHED"}).status_code == 422

    flag = call(teacher, "POST", f"{base}/{challenge_id}/flags", json={"strategy": "STATIC", "value": "CYBERLAB{ok}"})
    assert flag.status_code == 200
    assert call(teacher, "PUT", f"{base}/{challenge_id}", json={**body, "status": "PUBLISHED"}).status_code == 200
    # The last flag of a live challenge cannot be removed from under the students.
    assert call(teacher, "DELETE", f"{base}/{challenge_id}/flags/{flag.json()['id']}").status_code == 409


def test_hidden_scoreboard_is_hidden_from_learners_only(db: DbSession, call: Caller) -> None:
    from app import settings_service
    from app.models import SystemSetting

    admin = make_user(db, "board_admin", "ADMIN")
    learner = make_user(db, "board_learner", "STUDENT")
    for user in (admin, learner):
        make_role(db, user.roles[0].name, ("scoreboard.view",))
    db.add(SystemSetting(key="scoreboard_enabled", value=False, description="off"))
    db.flush()
    settings_service._cache.pop("scoreboard_enabled", None)
    try:
        assert call(learner, "GET", "/api/v1/ctf/scoreboard").status_code == 403
        staff = call(admin, "GET", "/api/v1/ctf/scoreboard")
        assert staff.status_code == 200
        assert staff.json()["frozen"] is False
    finally:
        settings_service._cache.pop("scoreboard_enabled", None)


def test_rankings_are_hidden_from_learners_by_default(db: DbSession, call: Caller) -> None:
    """SPEC §4/§7.5: students never see other students' scores unless the teacher turns rankings on."""
    from app import settings_service

    learner = make_user(db, "default_learner", "STUDENT")
    make_role(db, "STUDENT", ("scoreboard.view",))
    settings_service._cache.pop("scoreboard_enabled", None)
    try:
        assert call(learner, "GET", "/api/v1/ctf/scoreboard").status_code == 403
    finally:
        settings_service._cache.pop("scoreboard_enabled", None)
