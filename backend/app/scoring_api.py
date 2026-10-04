from datetime import datetime
from typing import Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import audit
from app.ctf_service import get_event, list_challenges
from app.dependencies import get_db, require_csrf, require_permission
from app.models import (
    Challenge,
    ChallengeFlag,
    ChallengeProgress,
    ChallengeSubmission,
    CtfEvent,
    Hint,
    HintUse,
    Notification,
    User,
    XpTransaction,
)
from app.scoring_service import (
    add_flag,
    freeze_scoreboard,
    get_scoreboard,
    grade_for_score,
    list_grade_scales,
    now_utc,
    pause_progress,
    progress_for_student,
    reset_progress,
    save_grade_scale,
    start_challenge,
    submit_flag,
    use_hint,
)
from app.settings_service import get as get_setting
from app.users_service import user_roles

router = APIRouter(prefix="/api/v1/ctf", tags=["scoring"])
class FlagInput(BaseModel):
    strategy: Literal["STATIC", "REGEX", "DYNAMIC_HMAC"]
    value: str | None = Field(default=None, max_length=256)
    flag_format: str | None = Field(default=None, max_length=255)


class SubmissionInput(BaseModel):
    flag: str = Field(min_length=1, max_length=256)


class GradeScaleInput(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    min_score: int = Field(ge=0, le=10000000)
    grade_value: float = Field(ge=0, le=100)
    label: str = Field(default="", max_length=80)
    sort_order: int = Field(default=0, ge=0, le=10000)


class FreezeInput(BaseModel):
    scope: Literal["GLOBAL", "CLASS", "EVENT"]
    scope_id: str = Field(default="0", max_length=64)
    frozen: bool


class PauseInput(BaseModel):
    paused: bool


def _student(actor: User) -> None:
    if "STUDENT" not in user_roles(actor):
        raise HTTPException(403, "student role required")


@router.get("/student/summary")
def student_summary(actor: User = Depends(require_permission("challenge.submit")), db: Session = Depends(get_db)) -> dict[str, object]:
    _student(actor)
    progress = list(db.scalars(select(ChallengeProgress).where(ChallengeProgress.user_id == actor.id)).all())
    solved = [row for row in progress if row.completed_at is not None]
    durations = [cast(int, progress_for_student(db, actor, challenge)["elapsed_seconds"]) for row in progress if (challenge := db.get(Challenge, row.challenge_id)) is not None]
    solved_durations = [cast(int, progress_for_student(db, actor, challenge)["elapsed_seconds"]) for row in solved if (challenge := db.get(Challenge, row.challenge_id)) is not None]
    xp = int(db.scalar(select(func.coalesce(func.sum(XpTransaction.points), 0)).where(XpTransaction.user_id == actor.id)) or 0)
    attempts = int(db.scalar(select(func.count()).select_from(ChallengeSubmission).where(ChallengeSubmission.user_id == actor.id)) or 0)
    hints = int(db.scalar(select(func.count()).select_from(HintUse).where(HintUse.user_id == actor.id)) or 0)
    history = []
    rows = db.execute(select(XpTransaction, Challenge.title, CtfEvent.name).join(Challenge, Challenge.id == XpTransaction.challenge_id).join(CtfEvent, CtfEvent.id == XpTransaction.event_id).where(XpTransaction.user_id == actor.id).order_by(XpTransaction.created_at.desc()).limit(30)).all()
    for transaction, title, event_name in rows:
        history.append({"type": transaction.source_type, "challenge": title, "event": event_name, "points": transaction.points, "created_at": transaction.created_at})
    failed_rows = db.execute(select(ChallengeSubmission, Challenge.title, CtfEvent.name).join(Challenge, Challenge.id == ChallengeSubmission.challenge_id).join(CtfEvent, CtfEvent.id == Challenge.event_id).where(ChallengeSubmission.user_id == actor.id, ChallengeSubmission.is_correct.is_(False)).order_by(ChallengeSubmission.attempted_at.desc()).limit(30)).all()
    history.extend({"type": "FAILED_ATTEMPT", "challenge": title, "event": event_name, "points": 0, "created_at": submission.attempted_at} for submission, title, event_name in failed_rows)
    history.sort(key=lambda row: cast(datetime, row["created_at"]), reverse=True)
    return {"xp": xp, "solved": len(solved), "started": len(progress), "total_seconds": sum(durations), "average_seconds": round(sum(solved_durations) / len(solved_durations)) if solved_durations else 0, "attempts": attempts, "hints": hints, "history": history}


@router.get("/student/notifications")
def student_notifications(actor: User = Depends(require_permission("challenge.submit")), db: Session = Depends(get_db)) -> dict[str, object]:
    _student(actor)
    rows = db.scalars(select(Notification).where(Notification.user_id == actor.id).order_by(Notification.created_at.desc(), Notification.id.desc()).limit(50)).all()
    return {"items": [{"id": row.id, "type": row.event_type, "payload": row.payload, "created_at": row.created_at, "read": row.read_at is not None} for row in rows], "unread": sum(bool(row.read_at is None) for row in rows)}


@router.post("/student/notifications/read", dependencies=[Depends(require_csrf)])
def mark_notifications_read(actor: User = Depends(require_permission("challenge.submit")), db: Session = Depends(get_db)) -> dict[str, bool]:
    _student(actor)
    for row in db.scalars(select(Notification).where(Notification.user_id == actor.id, Notification.read_at.is_(None))).all():
        row.read_at = now_utc()
    db.commit()
    return {"ok": True}


def _student_challenge(db: Session, public_id: str) -> Challenge:
    item = db.scalar(select(Challenge).where(Challenge.public_id == public_id, Challenge.deleted_at.is_(None)))
    if item is None:
        raise HTTPException(404, "challenge unavailable")
    return item


def _admin_challenge(db: Session, actor: User, event_id: int, challenge_id: int) -> Challenge:
    event = get_event(db, actor, event_id)
    if event is None:
        raise HTTPException(404, "challenge not found")
    item = next((row for row in list_challenges(db, event, include_archived=True) if row.id == challenge_id), None)
    if item is None:
        raise HTTPException(404, "challenge not found")
    return item


def _flag_data(item: ChallengeFlag) -> dict[str, object]:
    return {"id": item.id, "strategy": item.strategy, "flag_format": item.flag_format, "enabled": item.enabled}


@router.get("/events/{event_id}/challenges/{challenge_id}/flags")
def get_flags(event_id: int, challenge_id: int, actor: User = Depends(require_permission("challenge.update")), db: Session = Depends(get_db)) -> list[dict[str, object]]:
    item = _admin_challenge(db, actor, event_id, challenge_id)
    return [_flag_data(flag) for flag in db.scalars(select(ChallengeFlag).where(ChallengeFlag.challenge_id == item.id).order_by(ChallengeFlag.id)).all()]


@router.post("/events/{event_id}/challenges/{challenge_id}/flags", dependencies=[Depends(require_csrf)])
def post_flag(event_id: int, challenge_id: int, payload: FlagInput, actor: User = Depends(require_permission("challenge.update")), db: Session = Depends(get_db)) -> dict[str, object]:
    item = _admin_challenge(db, actor, event_id, challenge_id)
    try:
        flag = add_flag(db, item, payload.strategy, payload.value, payload.flag_format)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    audit.log(db, "CHALLENGE_FLAG_CREATED", actor.id, "challenge", item.public_id, {"strategy": flag.strategy})
    db.commit()
    return _flag_data(flag)


@router.delete("/events/{event_id}/challenges/{challenge_id}/flags/{flag_id}", dependencies=[Depends(require_csrf)])
def delete_flag(event_id: int, challenge_id: int, flag_id: int, actor: User = Depends(require_permission("challenge.update")), db: Session = Depends(get_db)) -> dict[str, bool]:
    item = _admin_challenge(db, actor, event_id, challenge_id)
    flag = db.scalar(select(ChallengeFlag).where(ChallengeFlag.id == flag_id, ChallengeFlag.challenge_id == item.id))
    if flag is None:
        raise HTTPException(404, "flag not found")
    db.delete(flag)
    audit.log(db, "CHALLENGE_FLAG_DELETED", actor.id, "challenge", item.public_id, {"flag_id": flag.id})
    db.commit()
    return {"ok": True}


@router.post("/challenges/{challenge_public_id}/start", dependencies=[Depends(require_csrf)])
@router.post("/student/challenges/{challenge_public_id}/start", dependencies=[Depends(require_csrf)])
def post_start(challenge_public_id: str, actor: User = Depends(require_permission("challenge.submit")), db: Session = Depends(get_db)) -> dict[str, object]:
    _student(actor)
    challenge = _student_challenge(db, challenge_public_id)
    try:
        progress = start_challenge(db, actor, challenge)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    db.commit()
    return progress_for_student(db, actor, challenge) | {"started_at": progress.started_at}


@router.post("/challenges/{challenge_public_id}/submit", dependencies=[Depends(require_csrf)])
@router.post("/student/challenges/{challenge_public_id}/submit", dependencies=[Depends(require_csrf)])
def post_submission(challenge_public_id: str, payload: SubmissionInput, request: Request, actor: User = Depends(require_permission("challenge.submit")), db: Session = Depends(get_db)) -> dict[str, object]:
    _student(actor)
    challenge = _student_challenge(db, challenge_public_id)
    try:
        result = submit_flag(db, actor, challenge, payload.flag, request.client.host if request.client else None)
    except LookupError as exc:
        raise HTTPException(404, "challenge unavailable") from exc
    except TimeoutError as exc:
        raise HTTPException(429, "submission rate limit reached") from exc
    except PermissionError as exc:
        raise HTTPException(429, "attempt limit reached") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    if result["correct"] and not result["already_solved"]:
        audit.log(db, "CHALLENGE_SOLVED", actor.id, "challenge", challenge.public_id, {"points": result["points_awarded"]})
    else:
        audit.log(db, "CHALLENGE_SUBMISSION", actor.id, "challenge", challenge.public_id, {"correct": result["correct"]})
    db.commit()
    result["progress"] = progress_for_student(db, actor, challenge)
    return result

class HintUseInput(BaseModel):
    hint_id: int = Field(ge=1)


@router.post("/challenges/{challenge_public_id}/hint", dependencies=[Depends(require_csrf)])
def post_hint(challenge_public_id: str, payload: HintUseInput, actor: User = Depends(require_permission("challenge.submit")), db: Session = Depends(get_db)) -> dict[str, object]:
    return _use_student_hint(challenge_public_id, payload.hint_id, actor, db)

@router.post("/student/challenges/{challenge_public_id}/hints/{hint_id}", dependencies=[Depends(require_csrf)])
def post_hint_use(challenge_public_id: str, hint_id: int, actor: User = Depends(require_permission("challenge.submit")), db: Session = Depends(get_db)) -> dict[str, object]:
    return _use_student_hint(challenge_public_id, hint_id, actor, db)

def _use_student_hint(challenge_public_id: str, hint_id: int, actor: User, db: Session) -> dict[str, object]:
    _student(actor)
    challenge = _student_challenge(db, challenge_public_id)
    try:
        result = use_hint(db, actor, challenge, hint_id)
    except LookupError as exc:
        raise HTTPException(404, "challenge unavailable") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    audit.log(db, "CHALLENGE_HINT_USED", actor.id, "challenge", challenge.public_id, {"hint_id": hint_id, "cost": result["cost"]})
    db.commit()
    return result


@router.get("/student/challenges/{challenge_public_id}/progress")
def get_progress(challenge_public_id: str, actor: User = Depends(require_permission("challenge.submit")), db: Session = Depends(get_db)) -> dict[str, object]:
    _student(actor)
    challenge = _student_challenge(db, challenge_public_id)
    from app.scoring_service import _student_can_access
    if not _student_can_access(db, actor, challenge):
        raise HTTPException(404, "challenge unavailable")
    progress = progress_for_student(db, actor, challenge)
    used_hints = db.execute(select(HintUse, Hint).join(Hint, Hint.id == HintUse.hint_id).where(HintUse.user_id == actor.id, HintUse.challenge_id == challenge.id).order_by(Hint.order)).all()
    event_limit = min(limit for limit in (int(get_setting(db, "max_attempts_global")), challenge.max_attempts, challenge.event.max_attempts) if limit is not None)
    progress["attempts_remaining"] = max(0, event_limit - cast(int, progress["attempts"])) if event_limit is not None else None
    progress["used_hints"] = [{"id": hint.id, "order": hint.order, "cost": use.cost, "content_markdown": hint.content_markdown} for use, hint in used_hints]
    progress["points_awarded"] = int(db.scalar(select(func.coalesce(func.sum(XpTransaction.points), 0)).where(XpTransaction.user_id == actor.id, XpTransaction.challenge_id == challenge.id, XpTransaction.source_type == "SOLVE")) or 0)
    return progress


@router.post("/instructor/events/{event_id}/challenges/{challenge_id}/progress/{student_id}/pause", dependencies=[Depends(require_csrf)])
def pause_student(event_id: int, challenge_id: int, student_id: int, payload: PauseInput, actor: User = Depends(require_permission("event.manage")), db: Session = Depends(get_db)) -> dict[str, object]:
    challenge = _admin_challenge(db, actor, event_id, challenge_id)
    student = db.get(User, student_id)
    if student is None or "STUDENT" not in user_roles(student):
        raise HTTPException(404, "student not found")
    if "ADMIN" not in user_roles(actor) and not any(cls.teacher_user_id == actor.id and cls in event.classes for cls in student.enrolled_classes for event in [challenge.event]):
        raise HTTPException(404, "student not found")
    try:
        row = pause_progress(db, student_id, challenge, payload.paused)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    db.commit()
    return {"paused": row.paused_at is not None, "paused_at": row.paused_at}


@router.post("/instructor/events/{event_id}/challenges/{challenge_id}/progress/{student_id}/reset", dependencies=[Depends(require_csrf)])
def reset_student(event_id: int, challenge_id: int, student_id: int, actor: User = Depends(require_permission("event.manage")), db: Session = Depends(get_db)) -> dict[str, bool]:
    challenge = _admin_challenge(db, actor, event_id, challenge_id)
    student = db.get(User, student_id)
    if student is None or "STUDENT" not in user_roles(student):
        raise HTTPException(404, "student not found")
    if "ADMIN" not in user_roles(actor) and not any(cls.teacher_user_id == actor.id and cls in challenge.event.classes for cls in student.enrolled_classes):
        raise HTTPException(404, "student not found")
    reset_progress(db, student_id, challenge)
    audit.log(db, "CHALLENGE_PROGRESS_RESET", actor.id, "challenge", challenge.public_id, {"student_id": student_id})
    db.commit()
    return {"ok": True}


@router.get("/grade-scales")
def get_grade_scales(actor: User = Depends(require_permission("challenge.view")), db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return [{"id": row.id, "name": row.name, "min_score": row.min_score, "grade_value": row.grade_value, "label": row.label, "sort_order": row.sort_order} for row in list_grade_scales(db)]


@router.post("/grade-scales", dependencies=[Depends(require_csrf)])
def post_grade_scale(payload: GradeScaleInput, actor: User = Depends(require_permission("scoreboard.manage")), db: Session = Depends(get_db)) -> dict[str, object]:
    return _save_grade_scale(db, actor, None, payload)


@router.put("/grade-scales/{item_id}", dependencies=[Depends(require_csrf)])
def put_grade_scale(item_id: int, payload: GradeScaleInput, actor: User = Depends(require_permission("scoreboard.manage")), db: Session = Depends(get_db)) -> dict[str, object]:
    return _save_grade_scale(db, actor, item_id, payload)


def _save_grade_scale(db: Session, actor: User, item_id: int | None, payload: GradeScaleInput) -> dict[str, object]:
    try:
        item = save_grade_scale(db, item_id, **payload.model_dump())
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(409, "grade scale name already exists") from exc
    audit.log(db, "GRADE_SCALE_SAVED", actor.id, "grade_scale", str(item.id))
    db.commit()
    return {"id": item.id, "name": item.name, "min_score": item.min_score, "grade_value": item.grade_value, "label": item.label, "sort_order": item.sort_order}


@router.get("/scoreboard")
def scoreboard(scope: Literal["GLOBAL", "CLASS", "EVENT"] = Query(default="GLOBAL"), scope_id: str = Query(default="0", max_length=64), actor: User = Depends(require_permission("scoreboard.view")), db: Session = Depends(get_db)) -> dict[str, object]:
    if not get_setting(db, "scoreboard_enabled"):
        raise HTTPException(403, "scoreboard is disabled")
    if scope == "EVENT":
        event = db.scalar(select(CtfEvent).where(CtfEvent.public_id == scope_id))
        if event is None:
            raise HTTPException(404, "event not found")
        scope_id = str(event.id)
        if "STUDENT" in user_roles(actor):
            from app.ctf_service import student_events
            if event not in student_events(db, actor):
                raise HTTPException(404, "event not found")
        elif "ADMIN" not in user_roles(actor) and get_event(db, actor, event.id) is None:
            raise HTTPException(404, "event not found")
    elif scope == "CLASS":
        if not scope_id.isdigit():
            raise HTTPException(422, "class scope_id must be numeric")
        class_id = int(scope_id)
        if "STUDENT" in user_roles(actor):
            if class_id not in {item.id for item in actor.enrolled_classes}:
                raise HTTPException(404, "class not found")
        elif "ADMIN" not in user_roles(actor):
            from app.models import SchoolClass
            school_class = db.get(SchoolClass, class_id)
            if school_class is None or school_class.teacher_user_id != actor.id:
                raise HTTPException(404, "class not found")
    elif scope == "GLOBAL" and "INSTRUCTOR" in user_roles(actor) and "ADMIN" not in user_roles(actor):
        raise HTTPException(403, "instructors must select an assigned class or event")
    rows = get_scoreboard(db, scope, scope_id)
    return {"scope": scope, "scope_id": scope_id, "items": [{**row, "grade": grade_for_score(db, cast(int, row["score"]))} for row in rows]}


@router.post("/scoreboard/freeze", dependencies=[Depends(require_csrf)])
def set_freeze(payload: FreezeInput, actor: User = Depends(require_permission("scoreboard.manage")), db: Session = Depends(get_db)) -> dict[str, object]:
    scope_id = payload.scope_id
    if "ADMIN" not in user_roles(actor):
        if payload.scope == "GLOBAL":
            raise HTTPException(403, "instructors cannot freeze the global scoreboard")
        if payload.scope == "EVENT":
            event_access = db.scalar(select(CtfEvent).where(CtfEvent.public_id == payload.scope_id))
            if event_access is None or get_event(db, actor, event_access.id) is None:
                raise HTTPException(404, "event not found")
        if payload.scope == "CLASS":
            if not payload.scope_id.isdigit():
                raise HTTPException(422, "class scope_id must be numeric")
            from app.models import SchoolClass
            assigned = db.get(SchoolClass, int(payload.scope_id))
            if assigned is None or assigned.teacher_user_id != actor.id:
                raise HTTPException(404, "class not found")
    if payload.scope == "GLOBAL":
        scope_id = "0"
    elif payload.scope == "EVENT":
        event = db.scalar(select(CtfEvent).where(CtfEvent.public_id == payload.scope_id))
        if event is None:
            raise HTTPException(404, "event not found")
        scope_id = str(event.id)
        event.scoreboard_frozen = payload.frozen
    elif not scope_id.isdigit():
        raise HTTPException(422, "class scope_id must be numeric")
    snapshot = freeze_scoreboard(db, payload.scope, scope_id, payload.frozen)
    audit.log(db, "SCOREBOARD_FROZEN" if payload.frozen else "SCOREBOARD_UNFROZEN", actor.id, "scoreboard", f"{payload.scope}:{scope_id}")
    db.commit()
    return {"scope": payload.scope, "scope_id": scope_id, "frozen": payload.frozen, "items": snapshot}
