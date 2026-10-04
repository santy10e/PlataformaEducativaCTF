from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.ctf_service import create_hint, save_challenge, save_event, save_taxonomy
from app.database import Base
from app.models import (
    Category,
    Challenge,
    ChallengeSubmission,
    CtfEvent,
    Difficulty,
    Notification,
    Permission,
    Role,
    SchoolClass,
    User,
    XpTransaction,
)
from app.scoring_service import (
    SubmissionRateLimiter,
    _matches,
    _solve_locks,
    add_flag,
    get_scoreboard,
    grade_for_score,
    start_challenge,
    submission_limiter,
    submit_flag,
    use_hint,
)


def setup_round(db: Session, *, max_attempts: int | None = None, strategy: str = "FIXED", config: dict[str, object] | None = None) -> tuple[User, CtfEvent, Challenge]:
    role = db.scalar(select(Role).where(Role.name == "STUDENT"))
    if role is None:
        role = Role(name="STUDENT", is_system=True)
        db.add(role)
        db.flush()
    admin_role = db.scalar(select(Role).where(Role.name == "ADMIN"))
    if admin_role is None:
        admin_role = Role(name="ADMIN", is_system=True)
        db.add(admin_role)
        db.flush()
    admin = User(username=f"admin{datetime.now(UTC).microsecond}", password_hash="unused", display_name="Admin", roles=[admin_role], is_active=True)
    db.add(admin)
    db.flush()
    student = User(username=f"learner{datetime.now(UTC).microsecond}", password_hash="unused", display_name="Learner", roles=[role], is_active=True)
    school_class = SchoolClass(name=f"Class{datetime.now(UTC).microsecond}", students=[student])
    db.add(school_class)
    db.flush()
    now = datetime.now(UTC)
    event = save_event(db, admin, None, name="Scoring round", status="PUBLISHED", visibility="ASSIGNED", mode="JEOPARDY", rules_markdown="", starts_at=now - timedelta(minutes=5), ends_at=now + timedelta(hours=1), class_ids=[school_class.id], scoring_strategy=strategy, scoring_config=config or {}, max_attempts=max_attempts)
    category = save_taxonomy(db, Category, None, name=f"Cat{datetime.now(UTC).microsecond}", color="#123456", sort_order=0, multiplier=1.0)
    difficulty = save_taxonomy(db, Difficulty, None, name=f"Diff{datetime.now(UTC).microsecond}", color="#654321", sort_order=0, multiplier=1.0)
    challenge = save_challenge(db, event, None, category_id=category.id, difficulty_id=difficulty.id, slug=f"task-{datetime.now(UTC).microsecond}", title="Task", description_markdown="Solve it", status="PUBLISHED", points=100, sort_order=0, delivery_type="STATIC", delivery_config={}, module_id=None, flag_hash=None, prerequisite_ids=[], max_attempts=max_attempts)
    db.flush()
    return student, event, challenge


def test_static_flag_hash_start_is_idempotent_and_solve_is_not_recounted(db: Session) -> None:
    submission_limiter._attempts.clear()
    student, _event, challenge = setup_round(db)
    stored = add_flag(db, challenge, "STATIC", "CYBER{static-answer}", None)
    assert stored.matcher != "CYBER{static-answer}"
    first = start_challenge(db, student, challenge)
    second = start_challenge(db, student, challenge)
    assert first.started_at == second.started_at
    solved = submit_flag(db, student, challenge, "CYBER{static-answer}", "10.0.0.10")
    repeated = submit_flag(db, student, challenge, "CYBER{static-answer}", "10.0.0.10")
    assert solved["correct"] is True and solved["points_awarded"] == 100
    assert repeated["already_solved"] is True and repeated["points_awarded"] == 0
    assert db.scalar(select(func.count()).select_from(XpTransaction).where(XpTransaction.source_type == "SOLVE")) == 1
    assert db.scalar(select(func.count()).select_from(Notification).where(Notification.event_type == "CHALLENGE_SOLVED")) == 1


def test_regex_and_dynamic_hmac_flags_are_validated_and_student_bound(db: Session) -> None:
    from app.models import User as UserModel
    student, _event, challenge = setup_round(db)
    other = UserModel(username="other-hmac-student", password_hash="unused", display_name="Other", is_active=True)
    db.add(other)
    db.flush()
    regex_flag = add_flag(db, challenge, "REGEX", r"CYBER\{[A-Z0-9]{8}\}", None)
    dynamic = add_flag(db, challenge, "DYNAMIC_HMAC", None, "CYBER{{digest}}")
    assert _matches(regex_flag, challenge, student, "CYBER{AB12CD34}")
    assert not _matches(regex_flag, challenge, student, "CYBER{bad}")
    assert dynamic.matcher is None
    first = "CYBER{" + __import__("hmac").new(__import__("app.config", fromlist=["settings"]).settings.effective_flag_hmac_secret.encode(), f"{student.id}|{challenge.id}|{dynamic.id}".encode(), __import__("hashlib").sha256).hexdigest() + "}"
    assert _matches(dynamic, challenge, student, first)
    assert not _matches(dynamic, challenge, other, first)
    with pytest.raises(ValueError, match="unsafe"):
        add_flag(db, challenge, "REGEX", r"(a+)+$", None)
    with pytest.raises(ValueError, match="unsafe"):
        add_flag(db, challenge, "REGEX", r"(a|aa)+$", None)


def test_limit_of_attempts_is_enforced_and_attempt_values_are_not_stored(db: Session) -> None:
    submission_limiter._attempts.clear()
    student, _event, challenge = setup_round(db, max_attempts=1)
    add_flag(db, challenge, "STATIC", "right", None)
    start_challenge(db, student, challenge)
    assert submit_flag(db, student, challenge, "wrong", "10.0.0.11")["correct"] is False
    with pytest.raises(PermissionError, match="attempt limit"):
        submit_flag(db, student, challenge, "right", "10.0.0.11")
    row = db.scalar(select(ChallengeSubmission))
    assert row is not None and row.submission_hash != "wrong"
    assert db.scalar(select(func.count()).select_from(Notification).where(Notification.event_type == "SUBMISSION_FAILED")) == 1


def test_hints_must_be_ordered_and_cost_is_deducted_from_score(db: Session) -> None:
    submission_limiter._attempts.clear()
    student, _event, challenge = setup_round(db)
    add_flag(db, challenge, "STATIC", "answer", None)
    first = create_hint(db, challenge, order=0, cost=10, content_markdown="First nudge")
    second = create_hint(db, challenge, order=1, cost=20, content_markdown="Second nudge")
    start_challenge(db, student, challenge)
    with pytest.raises(ValueError, match="in order"):
        use_hint(db, student, challenge, second.id)
    assert use_hint(db, student, challenge, first.id)["content_markdown"] == "First nudge"
    assert db.scalar(select(func.count()).select_from(Notification).where(Notification.event_type == "HINT_USED")) == 1
    submit_flag(db, student, challenge, "answer", "10.0.0.12")
    assert db.scalar(select(func.sum(XpTransaction.points))) == 90


def test_time_decay_uses_server_clock_and_ignores_client_time(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.scoring_service as service
    submission_limiter._attempts.clear()
    student, _event, challenge = setup_round(db, strategy="TIME_DECAY", config={"window_seconds": 600, "minimum_ratio": 0.2})
    add_flag(db, challenge, "STATIC", "answer", None)
    base_time = service.now_utc()
    monkeypatch.setattr(service, "now_utc", lambda: base_time)
    start_challenge(db, student, challenge)
    monkeypatch.setattr(service, "now_utc", lambda: base_time + timedelta(seconds=300))
    result = submit_flag(db, student, challenge, "answer", "10.0.0.13")
    assert result["points_awarded"] == 50


def test_grade_scale_thresholds_and_scoreboard_ties_and_freeze(db: Session) -> None:
    from app.scoring_service import freeze_scoreboard, save_grade_scale
    first, event, challenge = setup_round(db)
    second = User(username="tied-learner", password_hash="unused", display_name="Learner", is_active=True)
    db.add(second)
    db.flush()
    save_grade_scale(db, None, name="College", min_score=0, grade_value=1.0, label="Entry", sort_order=0)
    save_grade_scale(db, None, name="College", min_score=100, grade_value=5.0, label="Top", sort_order=1)
    assert grade_for_score(db, 105) == {"grade": 5.0, "label": "Top", "scale": "College"}
    db.add_all([
        XpTransaction(user_id=first.id, event_id=event.id, challenge_id=challenge.id, source_type="BONUS", source_id=1, points=100),
        XpTransaction(user_id=second.id, event_id=event.id, challenge_id=challenge.id, source_type="BONUS", source_id=1, points=100),
    ])
    db.flush()
    board = get_scoreboard(db, "EVENT", str(event.id))
    assert [row["rank"] for row in board] == [1, 1]
    frozen = freeze_scoreboard(db, "EVENT", str(event.id), True)
    db.add(XpTransaction(user_id=first.id, event_id=event.id, challenge_id=challenge.id, source_type="LATE", source_id=2, points=25))
    db.flush()
    assert get_scoreboard(db, "EVENT", str(event.id)) == frozen


def test_concurrent_correct_submissions_create_one_solve_transaction(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'parallel.db'}", connect_args={"timeout": 30})
    Base.metadata.create_all(engine)
    submission_limiter._attempts.clear()
    with Session(engine, expire_on_commit=False) as db:
        student, _event, challenge = setup_round(db)
        add_flag(db, challenge, "STATIC", "parallel-answer", None)
        db.commit()
        start_challenge(db, student, challenge)
        db.commit()
        student_id, challenge_id = student.id, challenge.id
    def submit_once() -> dict[str, object]:
        with Session(engine, expire_on_commit=False) as db:
            return submit_flag(db, db.get(User, student_id), db.get(Challenge, challenge_id), "parallel-answer", "10.0.0.20")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _index: submit_once(), range(2)))
    with Session(engine) as db:
        assert sum(int(result["points_awarded"]) for result in results) == 100
        assert db.scalar(select(func.count()).select_from(XpTransaction).where(XpTransaction.source_type == "SOLVE")) == 1
        assert db.scalar(select(func.count()).select_from(ChallengeSubmission).where(ChallengeSubmission.is_correct.is_(True))) == 1
    assert (student_id, challenge_id) not in _solve_locks
    engine.dispose()


def test_twenty_students_can_submit_concurrently(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'classroom-load.db'}", connect_args={"timeout": 30})
    Base.metadata.create_all(engine)
    submission_limiter._attempts.clear()
    with Session(engine, expire_on_commit=False) as db:
        student, _event, challenge = setup_round(db)
        school_class = db.scalar(select(SchoolClass).where(SchoolClass.students.any(User.id == student.id)))
        assert school_class is not None
        learners = [student]
        for index in range(19):
            learner = User(username=f"load-learner-{index}", password_hash="unused", display_name=f"Learner {index}", is_active=True)
            school_class.students.append(learner)
            learners.append(learner)
        add_flag(db, challenge, "STATIC", "classroom-answer", None)
        db.flush()
        learner_ids = [learner.id for learner in learners]
        for learner in learners:
            start_challenge(db, learner, challenge)
        db.commit()
        challenge_id = challenge.id

    def submit_once(request: tuple[int, int]) -> dict[str, object]:
        _index, learner_id = request
        with Session(engine, expire_on_commit=False) as db:
            return submit_flag(db, db.get(User, learner_id), db.get(Challenge, challenge_id), "classroom-answer", "10.0.0.20")

    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(submit_once, enumerate(learner_ids)))
    assert len(results) == 20
    assert all(result["correct"] is True for result in results)
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(XpTransaction).where(XpTransaction.source_type == "SOLVE")) == 20
    engine.dispose()


def test_submission_rate_limiter_separates_student_and_proxy_bursts() -> None:
    limiter = SubmissionRateLimiter()
    for index in range(60):
        assert limiter.allow((f"user:{index}", "ip:school-proxy"), 8, now=float(index) / 100)
    assert not limiter.allow(("user:overflow", "ip:school-proxy"), 8, now=0.7)

    student_limiter = SubmissionRateLimiter()
    for index in range(8):
        assert student_limiter.allow(("user:student", "ip:school-proxy"), 8, now=float(index))
    assert not student_limiter.allow(("user:student", "ip:school-proxy"), 8, now=8.0)

    bounded = SubmissionRateLimiter(max_keys=3)
    assert bounded.allow(("user:one", "ip:shared"), 8, now=0.0)
    assert bounded.allow(("user:two", "ip:shared"), 8, now=0.1)
    assert not bounded.allow(("user:three", "ip:shared"), 8, now=0.2)
    assert len(bounded._attempts) == 3
def test_pause_and_reset_are_server_controlled(db: Session) -> None:
    from app.scoring_service import pause_progress, progress_for_student, reset_progress
    student, _event, challenge = setup_round(db)
    add_flag(db, challenge, "STATIC", "pause-answer", None)
    start_challenge(db, student, challenge)
    paused = pause_progress(db, student.id, challenge, True)
    assert paused.paused_at is not None
    pause_progress(db, student.id, challenge, False)
    assert progress_for_student(db, student, challenge)["paused"] is False
    reset_progress(db, student.id, challenge)
    assert progress_for_student(db, student, challenge)["started_at"] is None


def test_invalid_scoring_configuration_is_rejected(db: Session) -> None:
    from app.ctf_service import _validated_scoring_config
    with pytest.raises(ValueError, match="window_seconds"):
        _validated_scoring_config("TIME_DECAY", {"window_seconds": 1})
    with pytest.raises(ValueError, match="unsupported"):
        _validated_scoring_config("FIXED", {"query": "not allowed"})
def test_student_api_start_submit_and_safe_challenge_response(db: Session) -> None:
    from fastapi.testclient import TestClient

    from app.dependencies import current_session, get_db
    from app.main import app
    from app.models import Session as AuthSession
    from app.security import digest_token
    student, event, challenge = setup_round(db)
    add_flag(db, challenge, "STATIC", "api-answer", None)
    student.roles[0].permissions = [Permission(code="challenge.submit", description="Submit answers"), Permission(code="challenge.view", description="View challenges"), Permission(code="scoreboard.view", description="View scoreboard")]
    token = "csrf-test-token"
    auth_session = AuthSession(user_id=student.id, token_hash=digest_token("api-session"), csrf_hash=digest_token(token), csrf_token=token, expires_at=datetime(2099, 1, 1, tzinfo=UTC).replace(tzinfo=None))
    app.dependency_overrides[current_session] = lambda: (student, auth_session)
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        headers = {"x-csrf-token": token}
        visible = client.get(f"/api/v1/ctf/student/events/{event.public_id}/challenges")
        assert visible.status_code == 200
        challenge_data = visible.json()[0]
        assert challenge_data["public_id"] == challenge.public_id
        assert all(secret not in challenge_data for secret in ("flag_hash", "flags", "hints", "delivery_config", "id"))
        started = client.post(f"/api/v1/ctf/challenges/{challenge.public_id}/start", headers=headers)
        assert started.status_code == 200
        submitted = client.post(f"/api/v1/ctf/challenges/{challenge.public_id}/submit", headers=headers, json={"flag": "api-answer", "started_at": "1900-01-01T00:00:00Z"})
        assert submitted.status_code == 200 and submitted.json()["points_awarded"] == 100
        repeated = client.post(f"/api/v1/ctf/challenges/{challenge.public_id}/submit", headers=headers, json={"flag": "api-answer"})
        assert repeated.status_code == 200 and repeated.json()["already_solved"] is True
        summary = client.get("/api/v1/ctf/student/summary")
        assert summary.status_code == 200
        assert summary.json()["xp"] == 100 and summary.json()["solved"] == 1
        notifications = client.get("/api/v1/ctf/student/notifications")
        assert notifications.status_code == 200 and notifications.json()["unread"] == 1
        assert notifications.json()["items"][0]["type"] == "CHALLENGE_SOLVED"
        marked = client.post("/api/v1/ctf/student/notifications/read", headers=headers)
        assert marked.status_code == 200 and client.get("/api/v1/ctf/student/notifications").json()["unread"] == 0
    finally:
        app.dependency_overrides.clear()
