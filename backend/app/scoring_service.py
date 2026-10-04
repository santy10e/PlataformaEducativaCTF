import hashlib
import hmac
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.events import event_bus
from app.models import (
    Challenge,
    ChallengeFlag,
    ChallengeProgress,
    ChallengeSubmission,
    CtfEvent,
    GradeScale,
    Hint,
    HintUse,
    Notification,
    ScoreboardFreeze,
    User,
    XpTransaction,
)
from app.settings_service import get as get_setting


def now_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SubmissionRateLimiter:
    def __init__(self, max_keys: int = 10_000) -> None:
        self._attempts: dict[str, list[float]] = {}
        self._max_keys = max_keys
        self._last_trim = float("-inf")
        self._lock = Lock()

    def allow(self, keys: tuple[str, ...], limit: int, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        with self._lock:
            self._trim(current)
            allowed = True
            for key in keys:
                if key not in self._attempts and len(self._attempts) >= self._max_keys:
                    allowed = False
                    continue
                recent = [value for value in self._attempts.get(key, []) if current - value < 60]
                key_limit = max(limit, 60) if key.startswith("ip:") else limit
                if len(recent) >= key_limit:
                    allowed = False
                recent.append(current)
                self._attempts[key] = recent
            self._trim(current)
            return allowed

    def _trim(self, current: float) -> None:
        if len(self._attempts) < self._max_keys or current - self._last_trim < 60:
            return
        self._last_trim = current
        expired = [key for key, stamps in self._attempts.items() if not stamps or current - stamps[-1] >= 60]
        for key in expired:
            self._attempts.pop(key, None)


submission_limiter = SubmissionRateLimiter()
_solve_locks: dict[tuple[int, int], Lock] = {}
_solve_lock_users: dict[tuple[int, int], int] = {}
_solve_locks_guard = Lock()


def validate_regex(pattern: str) -> None:
    if not pattern or len(pattern) > 256:
        raise ValueError("regex must contain 1 to 256 characters")
    if re.search(r"\\[1-9]|\(\?[=!<]|\)[+*{]|\([^)]*[+*][^)]*\)[+*{]", pattern):
        raise ValueError("regex uses an unsupported or unsafe construct")
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValueError("invalid regex") from exc


def add_flag(db: Session, challenge: Challenge, strategy: str, value: str | None, flag_format: str | None) -> ChallengeFlag:
    if strategy not in FLAG_STRATEGIES:
        raise ValueError("unsupported flag strategy")
    matcher: str | None = None
    if strategy == "STATIC":
        if not value or len(value) > 256:
            raise ValueError("static flag must contain 1 to 256 characters")
        matcher = hashlib.sha256(value.encode()).hexdigest()
    elif strategy == "REGEX":
        if value is None:
            raise ValueError("regex pattern is required")
        validate_regex(value)
        matcher = value
    elif flag_format is None or "{digest}" not in flag_format or len(flag_format) > 255:
        raise ValueError("dynamic format must include {digest}")
    item = ChallengeFlag(challenge_id=challenge.id, strategy=strategy, matcher=matcher, flag_format=flag_format)
    db.add(item)
    db.flush()
    return item


def _verify_static(flag: ChallengeFlag, challenge: Challenge, user: User, submitted: str) -> bool:
    del challenge, user
    if flag.matcher is None:
        return False
    candidate = hashlib.sha256(submitted.encode()).hexdigest()
    return hmac.compare_digest(candidate, flag.matcher)


def _verify_regex(flag: ChallengeFlag, challenge: Challenge, user: User, submitted: str) -> bool:
    del challenge, user
    if flag.matcher is None:
        return False
    try:
        return re.fullmatch(flag.matcher, submitted, flags=re.ASCII) is not None
    except re.error:
        return False


def _verify_dynamic_hmac(flag: ChallengeFlag, challenge: Challenge, user: User, submitted: str) -> bool:
    if flag.flag_format is None:
        return False
    raw = f"{user.id}|{challenge.id}|{flag.id}".encode()
    digest = hmac.new(settings.effective_flag_hmac_secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(flag.flag_format.replace("{digest}", digest), submitted)


FlagVerifier = Callable[[ChallengeFlag, Challenge, User, str], bool]
FLAG_STRATEGIES: dict[str, FlagVerifier] = {
    "STATIC": _verify_static,
    "REGEX": _verify_regex,
    "DYNAMIC_HMAC": _verify_dynamic_hmac,
}


def _matches(flag: ChallengeFlag, challenge: Challenge, user: User, submitted: str) -> bool:
    verifier = FLAG_STRATEGIES.get(flag.strategy)
    return verifier(flag, challenge, user, submitted) if verifier is not None else False

def _event_is_active(event: CtfEvent) -> bool:
    now = now_utc()
    return event.status == "PUBLISHED" and event.deleted_at is None and (event.starts_at is None or event.starts_at <= now) and (event.ends_at is None or now < event.ends_at)


def _completed_ids(db: Session, user_id: int, challenge: Challenge) -> set[int]:
    required = {item.id for item in challenge.prerequisites}
    if not required:
        return set()
    return set(db.scalars(select(ChallengeProgress.challenge_id).where(
        ChallengeProgress.user_id == user_id,
        ChallengeProgress.completed_at.is_not(None),
        ChallengeProgress.challenge_id.in_(required),
    )).all())


def _student_can_access(db: Session, user: User, challenge: Challenge) -> bool:
    from app.ctf_service import student_events
    return challenge.status == "PUBLISHED" and challenge.deleted_at is None and challenge.event in student_events(db, user) and _completed_ids(db, user.id, challenge) == {item.id for item in challenge.prerequisites}


def _progress(db: Session, user: User, challenge: Challenge, create: bool) -> ChallengeProgress | None:
    row = db.scalar(select(ChallengeProgress).where(
        ChallengeProgress.user_id == user.id,
        ChallengeProgress.challenge_id == challenge.id,
    ).with_for_update())
    if row is None and create:
        row = ChallengeProgress(user_id=user.id, challenge_id=challenge.id, started_at=now_utc())
        db.add(row)
        try:
            db.flush()
        except Exception:
            db.rollback()
            row = db.scalar(select(ChallengeProgress).where(
                ChallengeProgress.user_id == user.id,
                ChallengeProgress.challenge_id == challenge.id,
            ).with_for_update())
            if row is None:
                raise
    return row


def start_challenge(db: Session, user: User, challenge: Challenge) -> ChallengeProgress:
    if not _student_can_access(db, user, challenge):
        raise LookupError("challenge unavailable")
    row = _progress(db, user, challenge, True)
    assert row is not None
    db.flush()
    return row


def _attempt_limit(db: Session, event: CtfEvent, challenge: Challenge) -> int:
    limits = [int(get_setting(db, "max_attempts_global"))]
    if event.max_attempts is not None:
        limits.append(event.max_attempts)
    if challenge.max_attempts is not None:
        limits.append(challenge.max_attempts)
    return min(limits)


def _calculate_award(db: Session, challenge: Challenge, progress: ChallengeProgress, event: CtfEvent) -> int:
    category = challenge.category.multiplier
    difficulty = challenge.difficulty.multiplier
    base = challenge.points * category * difficulty
    strategy = challenge.scoring_strategy or event.scoring_strategy
    config: dict[str, Any] = dict(event.scoring_config or {})
    config.update(challenge.scoring_config or {})
    if strategy == "TIME_DECAY":
        elapsed = max(0, (now_utc() - progress.started_at).total_seconds() - progress.total_paused_seconds)
        window = max(60, int(config.get("window_seconds", 1800)))
        factor = max(float(config.get("minimum_ratio", 0.2)), 1.0 - elapsed / window)
        base *= factor
    elif strategy == "DYNAMIC_BY_SOLVES":
        solved = db.scalar(select(func.count()).select_from(ChallengeProgress).join(Challenge).where(
            Challenge.event_id == event.id,
            ChallengeProgress.completed_at.is_not(None),
        )) or 0
        factor = max(float(config.get("minimum_ratio", 0.2)), 1.0 - solved * float(config.get("decay_per_solve", 0.05)))
        base *= factor
    return max(0, round(base))


def _submit_flag_unlocked(db: Session, user: User, challenge: Challenge, submitted: str, ip: str | None) -> dict[str, object]:
    if not submitted or len(submitted) > 256:
        raise ValueError("invalid submission")
    event = challenge.event
    if not _student_can_access(db, user, challenge) or not _event_is_active(event):
        raise LookupError("challenge unavailable")
    limit = int(get_setting(db, "submission_rate_limit"))
    if not submission_limiter.allow((f"user:{user.id}", f"ip:{ip or 'unknown'}"), limit):
        raise TimeoutError("submission rate limit reached")
    progress = _progress(db, user, challenge, False)
    if progress is None:
        raise ValueError("start the challenge before submitting")
    if progress.paused_at is not None:
        raise ValueError("challenge is paused")
    if progress.completed_at is not None:
        return {"correct": True, "already_solved": True, "points_awarded": 0}
    count = db.scalar(select(func.count()).select_from(ChallengeSubmission).where(
        ChallengeSubmission.user_id == user.id,
        ChallengeSubmission.challenge_id == challenge.id,
    )) or 0
    if count >= _attempt_limit(db, event, challenge):
        raise PermissionError("attempt limit reached")
    flags = db.scalars(select(ChallengeFlag).where(ChallengeFlag.challenge_id == challenge.id, ChallengeFlag.enabled.is_(True))).all()
    correct = any(_matches(flag, challenge, user, submitted) for flag in flags)
    db.add(ChallengeSubmission(user_id=user.id, challenge_id=challenge.id, submission_hash=hashlib.sha256(submitted.encode()).hexdigest(), is_correct=correct, attempted_at=now_utc()))
    if not correct:
        db.add(Notification(user_id=user.id, event_type="SUBMISSION_FAILED", payload={"challenge_public_id": challenge.public_id}, created_at=now_utc()))
        event_bus.publish("submission_failed", {"user_id": user.id, "challenge_id": challenge.id})
        db.flush()
        return {"correct": False, "already_solved": False, "points_awarded": 0}
    points = _calculate_award(db, challenge, progress, event)
    progress.completed_at = now_utc()
    db.add(XpTransaction(user_id=user.id, event_id=event.id, challenge_id=challenge.id, source_type="SOLVE", source_id=challenge.id, points=points))
    db.add(Notification(user_id=user.id, event_type="CHALLENGE_SOLVED", payload={"challenge_public_id": challenge.public_id, "points": points}, created_at=now_utc()))
    db.flush()
    event_bus.publish("challenge_solved", {"user_id": user.id, "challenge_id": challenge.id, "points": points})
    return {"correct": True, "already_solved": False, "points_awarded": points}


def use_hint(db: Session, user: User, challenge: Challenge, hint_id: int) -> dict[str, object]:
    if not _student_can_access(db, user, challenge) or not _event_is_active(challenge.event):
        raise LookupError("challenge unavailable")
    progress = _progress(db, user, challenge, False)
    if progress is None or progress.completed_at is not None or progress.paused_at is not None:
        raise ValueError("challenge is not in progress")
    hints = list(db.scalars(select(Hint).where(Hint.challenge_id == challenge.id).order_by(Hint.order, Hint.id)).all())
    used = set(db.scalars(select(HintUse.hint_id).where(HintUse.user_id == user.id, HintUse.challenge_id == challenge.id)).all())
    next_hint = next((item for item in hints if item.id not in used), None)
    if next_hint is None or next_hint.id != hint_id:
        raise ValueError("hints must be unlocked in order")
    db.add(HintUse(user_id=user.id, challenge_id=challenge.id, hint_id=next_hint.id, cost=next_hint.cost, used_at=now_utc()))
    db.add(XpTransaction(user_id=user.id, event_id=challenge.event_id, challenge_id=challenge.id, source_type="HINT", source_id=next_hint.id, points=-next_hint.cost))
    db.add(Notification(user_id=user.id, event_type="HINT_USED", payload={"challenge_public_id": challenge.public_id, "hint_order": next_hint.order, "cost": next_hint.cost}, created_at=now_utc()))
    event_bus.publish("hint_used", {"user_id": user.id, "challenge_id": challenge.id, "hint_id": next_hint.id, "cost": next_hint.cost})
    db.flush()
    return {"id": next_hint.id, "content_markdown": next_hint.content_markdown, "cost": next_hint.cost, "order": next_hint.order}


def progress_for_student(db: Session, user: User, challenge: Challenge) -> dict[str, object]:
    row = _progress(db, user, challenge, False)
    attempts = db.scalar(select(func.count()).select_from(ChallengeSubmission).where(ChallengeSubmission.user_id == user.id, ChallengeSubmission.challenge_id == challenge.id)) or 0
    hints = db.scalar(select(func.count()).select_from(HintUse).where(HintUse.user_id == user.id, HintUse.challenge_id == challenge.id)) or 0
    if row is None:
        return {"started_at": None, "completed_at": None, "elapsed_seconds": 0, "attempts": attempts, "hints_used": hints, "paused": False}
    end = row.completed_at or now_utc()
    paused = row.total_paused_seconds
    if row.paused_at is not None:
        paused += max(0, int((end - row.paused_at).total_seconds()))
    elapsed = max(0, int((end - row.started_at).total_seconds()) - paused)
    return {"started_at": row.started_at, "completed_at": row.completed_at, "elapsed_seconds": elapsed, "attempts": attempts, "hints_used": hints, "paused": row.paused_at is not None}


def pause_progress(db: Session, user_id: int, challenge: Challenge, paused: bool) -> ChallengeProgress:
    user = db.get(User, user_id)
    if user is None:
        raise LookupError("student not found")
    row = _progress(db, user, challenge, False)
    if row is None or row.completed_at is not None:
        raise LookupError("active challenge progress not found")
    now = now_utc()
    if paused and row.paused_at is None:
        row.paused_at = now
    elif not paused and row.paused_at is not None:
        row.total_paused_seconds += max(0, int((now - row.paused_at).total_seconds()))
        row.paused_at = None
    db.flush()
    return row


def reset_progress(db: Session, user_id: int, challenge: Challenge) -> None:
    db.execute(delete(ChallengeSubmission).where(ChallengeSubmission.user_id == user_id, ChallengeSubmission.challenge_id == challenge.id))
    db.execute(delete(HintUse).where(HintUse.user_id == user_id, HintUse.challenge_id == challenge.id))
    db.execute(delete(XpTransaction).where(XpTransaction.user_id == user_id, XpTransaction.challenge_id == challenge.id))
    db.execute(delete(ChallengeProgress).where(ChallengeProgress.user_id == user_id, ChallengeProgress.challenge_id == challenge.id))
    db.flush()


def _score_query(db: Session, scope: str, scope_id: str) -> list[dict[str, object]]:
    query = select(User.id, User.display_name, func.coalesce(func.sum(XpTransaction.points), 0).label("score")).join(XpTransaction, XpTransaction.user_id == User.id)
    if scope == "EVENT":
        query = query.where(XpTransaction.event_id == int(scope_id))
    elif scope == "CLASS":
        from app.models import class_students
        query = query.join(class_students, class_students.c.student_user_id == User.id).where(class_students.c.class_id == int(scope_id))
    rows = db.execute(query.group_by(User.id, User.display_name).order_by(func.sum(XpTransaction.points).desc(), User.display_name, User.id)).all()
    output: list[dict[str, object]] = []
    last_score: int | None = None
    rank = 0
    for position, row in enumerate(rows, start=1):
        score = int(row.score or 0)
        if score != last_score:
            rank = position
            last_score = score
        output.append({"rank": rank, "display_name": row.display_name, "score": score})
    return output


def get_scoreboard(db: Session, scope: str, scope_id: str) -> list[dict[str, object]]:
    freeze = db.get(ScoreboardFreeze, (scope, scope_id))
    if freeze is not None:
        return freeze.snapshot
    return _score_query(db, scope, scope_id)


def freeze_scoreboard(db: Session, scope: str, scope_id: str, freeze: bool) -> list[dict[str, object]]:
    row = db.get(ScoreboardFreeze, (scope, scope_id))
    if freeze:
        snapshot = _score_query(db, scope, scope_id)
        if row is None:
            row = ScoreboardFreeze(scope=scope, scope_id=scope_id, snapshot=snapshot)
            db.add(row)
        else:
            row.snapshot = snapshot
            row.frozen_at = now_utc()
        db.flush()
        return snapshot
    if row is not None:
        db.delete(row)
    return _score_query(db, scope, scope_id)


def grade_for_score(db: Session, score: int) -> dict[str, object] | None:
    item = db.scalar(select(GradeScale).where(GradeScale.min_score <= score).order_by(GradeScale.min_score.desc(), GradeScale.id).limit(1))
    return {"grade": item.grade_value, "label": item.label, "scale": item.name} if item else None


def save_grade_scale(db: Session, item_id: int | None, *, name: str, min_score: int, grade_value: float, label: str, sort_order: int) -> GradeScale:
    item = db.get(GradeScale, item_id) if item_id is not None else GradeScale()
    if item is None:
        raise LookupError("grade scale not found")
    item.name, item.min_score, item.grade_value, item.label, item.sort_order = name.strip(), min_score, grade_value, label.strip(), sort_order
    db.add(item)
    db.flush()
    return item


def list_grade_scales(db: Session) -> list[GradeScale]:
    return list(db.scalars(select(GradeScale).order_by(GradeScale.sort_order, GradeScale.min_score.desc())).all())
def submit_flag(db: Session, user: User, challenge: Challenge, submitted: str, ip: str | None) -> dict[str, object]:
    key = (user.id, challenge.id)
    with _solve_locks_guard:
        lock = _solve_locks.get(key)
        if lock is None:
            lock = Lock()
            _solve_locks[key] = lock
        _solve_lock_users[key] = _solve_lock_users.get(key, 0) + 1
    try:
        with lock:
            result = _submit_flag_unlocked(db, user, challenge, submitted, ip)
            db.commit()
            return result
    finally:
        with _solve_locks_guard:
            remaining_users = _solve_lock_users[key] - 1
            if remaining_users == 0:
                _solve_lock_users.pop(key)
                if _solve_locks.get(key) is lock:
                    _solve_locks.pop(key)
            else:
                _solve_lock_users[key] = remaining_users
