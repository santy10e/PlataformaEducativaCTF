"""Scoped and database-aggregated teacher reporting services."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import case, func, select, text
from sqlalchemy.orm import Session

from app.models import (
    Announcement,
    Category,
    Challenge,
    ChallengeProgress,
    ChallengeSubmission,
    CtfEvent,
    GradeScale,
    HintUse,
    SchoolClass,
    User,
    XpTransaction,
    class_students,
    ctf_event_classes,
)
from app.scoring_service import now_utc
from app.users_service import user_roles

ABANDONMENT_INACTIVITY_DAYS = 7


@dataclass(frozen=True)
class TeachingScope:
    class_ids: list[int]
    event_ids: list[int]
    resource_id: int
    resource_name: str


def _date_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value


def _apply_window(query: Any, column: Any, date_from: datetime | None, date_to: datetime | None) -> Any:
    start = _date_utc(date_from)
    end = _date_utc(date_to)
    if start is not None:
        query = query.where(column >= start)
    if end is not None:
        query = query.where(column <= end)
    return query


def resolve_scope(db: Session, actor: User, class_id: int | None, event_id: int | None) -> TeachingScope:
    if (class_id is None) == (event_id is None):
        raise HTTPException(422, "select exactly one class or event")
    is_admin = "ADMIN" in user_roles(actor)
    if class_id is not None:
        school_class = db.get(SchoolClass, class_id)
        if school_class is None or (not is_admin and school_class.teacher_user_id != actor.id):
            raise HTTPException(404, "class not found")
        events: list[int] = list(db.scalars(select(ctf_event_classes.c.event_id).where(ctf_event_classes.c.class_id == class_id)).all())
        return TeachingScope([class_id], [int(item) for item in events], school_class.id, school_class.name)

    event = db.get(CtfEvent, event_id)
    if event is None:
        raise HTTPException(404, "event not found")
    class_query = select(SchoolClass.id).join(ctf_event_classes, ctf_event_classes.c.class_id == SchoolClass.id).where(ctf_event_classes.c.event_id == event.id)
    if not is_admin:
        class_query = class_query.where(SchoolClass.teacher_user_id == actor.id)
    allowed_classes = [int(item) for item in db.scalars(class_query).all()]
    if not allowed_classes:
        raise HTTPException(404, "event not found")
    return TeachingScope(allowed_classes, [event.id], event.id, event.name)


def _students(db: Session, scope: TeachingScope, student_id: int | None) -> list[tuple[int, str]]:
    if not scope.class_ids:
        return []
    query = select(User.id, User.display_name).join(class_students, class_students.c.student_user_id == User.id).where(
        class_students.c.class_id.in_(scope.class_ids), User.is_active.is_(True)
    ).distinct().order_by(User.display_name, User.id)
    if student_id is not None:
        query = query.where(User.id == student_id)
    return [(int(row[0]), str(row[1])) for row in db.execute(query).all()]


def _grade_for_score(scales: list[GradeScale], score: int) -> dict[str, object] | None:
    for row in scales:
        if score >= row.min_score:
            return {"id": row.id, "name": row.name, "value": row.grade_value, "label": row.label}
    return None


def analytics(
    db: Session,
    actor: User,
    *,
    class_id: int | None,
    event_id: int | None,
    student_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    grade_scale_id: int | None = None,
) -> dict[str, Any]:
    start_date = _date_utc(date_from)
    end_date = _date_utc(date_to)
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(422, "date_from must be earlier than or equal to date_to")
    scope = resolve_scope(db, actor, class_id, event_id)
    students = _students(db, scope, student_id)
    student_ids = [student[0] for student in students]
    challenges = db.scalars(select(Challenge).where(Challenge.event_id.in_(scope.event_ids), Challenge.deleted_at.is_(None))).all() if scope.event_ids else []
    challenge_ids = [item.id for item in challenges]

    bind = db.get_bind()
    duration_seconds = (
        (func.julianday(ChallengeProgress.completed_at) - func.julianday(ChallengeProgress.started_at)) * 86400
        if bind.dialect.name == "sqlite"
        else func.timestampdiff(text("SECOND"), ChallengeProgress.started_at, ChallengeProgress.completed_at)
    ) - ChallengeProgress.total_paused_seconds
    progress_query = select(
        ChallengeProgress.user_id,
        func.count(ChallengeProgress.id),
        func.sum(case((ChallengeProgress.completed_at.is_not(None), 1), else_=0)),
        func.sum(case((ChallengeProgress.completed_at.is_(None), 1), else_=0)),
        func.sum(case((ChallengeProgress.completed_at.is_not(None), duration_seconds), else_=0)),
        func.sum(case((ChallengeProgress.completed_at.is_not(None), 1), else_=0)),
        func.max(func.coalesce(ChallengeProgress.completed_at, ChallengeProgress.started_at)),
    ).where(ChallengeProgress.user_id.in_(student_ids), ChallengeProgress.challenge_id.in_(challenge_ids)) if student_ids and challenge_ids else None
    submission_query = select(ChallengeSubmission.user_id, func.count(), func.sum(case((ChallengeSubmission.is_correct.is_(False), 1), else_=0)), func.max(ChallengeSubmission.attempted_at)).where(
        ChallengeSubmission.user_id.in_(student_ids), ChallengeSubmission.challenge_id.in_(challenge_ids)
    ) if student_ids and challenge_ids else None
    hint_query = select(HintUse.user_id, func.count()).where(HintUse.user_id.in_(student_ids), HintUse.challenge_id.in_(challenge_ids)) if student_ids and challenge_ids else None
    xp_query = select(XpTransaction.user_id, func.sum(XpTransaction.points)).where(XpTransaction.user_id.in_(student_ids), XpTransaction.event_id.in_(scope.event_ids)) if student_ids and scope.event_ids else None
    if progress_query is not None:
        progress_query = _apply_window(progress_query, ChallengeProgress.started_at, date_from, date_to).group_by(ChallengeProgress.user_id)
    if submission_query is not None:
        submission_query = _apply_window(submission_query, ChallengeSubmission.attempted_at, date_from, date_to).group_by(ChallengeSubmission.user_id)
    if hint_query is not None:
        hint_query = _apply_window(hint_query, HintUse.used_at, date_from, date_to).group_by(HintUse.user_id)
    if xp_query is not None:
        xp_query = _apply_window(xp_query, XpTransaction.created_at, date_from, date_to).group_by(XpTransaction.user_id)

    progress = {int(row[0]): row for row in db.execute(progress_query).all()} if progress_query is not None else {}
    submissions = {int(row[0]): row for row in db.execute(submission_query).all()} if submission_query is not None else {}
    hints = {int(row[0]): int(row[1] or 0) for row in db.execute(hint_query).all()} if hint_query is not None else {}
    scores = {int(row[0]): int(row[1] or 0) for row in db.execute(xp_query).all()} if xp_query is not None else {}

    scales_query = select(GradeScale).order_by(GradeScale.min_score.desc(), GradeScale.id)
    if grade_scale_id is not None:
        scales_query = scales_query.where(GradeScale.id == grade_scale_id)
    scales = list(db.scalars(scales_query).all())
    if grade_scale_id is not None and not scales:
        raise HTTPException(404, "grade scale not found")
    if grade_scale_id is None and scales:
        active_name = scales[0].name
        scales = [item for item in scales if item.name == active_name]

    student_rows: list[dict[str, Any]] = []
    completion_duration_total = 0.0
    completion_duration_count = 0
    total_started = total_completed = total_attempts = total_failures = total_hints = 0
    for user_id, name in students:
        p = progress.get(user_id)
        s = submissions.get(user_id)
        started = int(p[1] or 0) if p else 0
        completed = int(p[2] or 0) if p else 0
        attempts = int(s[1] or 0) if s else 0
        failures = int(s[2] or 0) if s else 0
        score = scores.get(user_id, 0)
        last_values = [value for value in ((p[6] if p else None), (s[3] if s else None)) if value is not None]
        last_activity = max(last_values) if last_values else None
        duration_total = float(p[4] or 0) if p else 0.0
        duration_count = int(p[5] or 0) if p else 0
        average_time = duration_total / duration_count if duration_count else 0.0
        completion_duration_total += duration_total
        completion_duration_count += duration_count
        total_started += started
        total_completed += completed
        total_attempts += attempts
        total_failures += failures
        total_hints += hints.get(user_id, 0)
        student_rows.append({
            "student_id": user_id, "display_name": name, "started": started, "completed": completed,
            "active": max(0, started - completed), "attempts": attempts, "failed_attempts": failures,
            "hints": hints.get(user_id, 0), "score": score, "grade": _grade_for_score(scales, score),
            "average_completion_seconds": round(average_time), "last_activity": last_activity,
        })

    progress_by_challenge = select(
        ChallengeProgress.challenge_id,
        func.count(ChallengeProgress.id),
        func.sum(case((ChallengeProgress.completed_at.is_not(None), 1), else_=0)),
    ).where(ChallengeProgress.user_id.in_(student_ids), ChallengeProgress.challenge_id.in_(challenge_ids)) if student_ids and challenge_ids else None
    failures_by_challenge = select(ChallengeSubmission.challenge_id, func.count()).where(
        ChallengeSubmission.user_id.in_(student_ids), ChallengeSubmission.challenge_id.in_(challenge_ids), ChallengeSubmission.is_correct.is_(False)
    ) if student_ids and challenge_ids else None
    if progress_by_challenge is not None:
        progress_by_challenge = _apply_window(progress_by_challenge, ChallengeProgress.started_at, date_from, date_to).group_by(ChallengeProgress.challenge_id)
    if failures_by_challenge is not None:
        failures_by_challenge = _apply_window(failures_by_challenge, ChallengeSubmission.attempted_at, date_from, date_to).group_by(ChallengeSubmission.challenge_id)
    p_challenge = {int(row[0]): (int(row[1] or 0), int(row[2] or 0)) for row in db.execute(progress_by_challenge).all()} if progress_by_challenge is not None else {}
    f_challenge = {int(row[0]): int(row[1] or 0) for row in db.execute(failures_by_challenge).all()} if failures_by_challenge is not None else {}

    cutoff = now_utc() - timedelta(days=ABANDONMENT_INACTIVITY_DAYS)
    last_submission = select(ChallengeSubmission.user_id.label("student_id"), ChallengeSubmission.challenge_id.label("challenge_id"), func.max(ChallengeSubmission.attempted_at).label("last_attempt")).where(
        ChallengeSubmission.user_id.in_(student_ids), ChallengeSubmission.challenge_id.in_(challenge_ids)
    ).group_by(ChallengeSubmission.user_id, ChallengeSubmission.challenge_id).subquery() if student_ids and challenge_ids else None
    abandoned_by_challenge: dict[int, int] = {}
    if last_submission is not None:
        stale_query = select(ChallengeProgress.challenge_id, func.count()).outerjoin(
            last_submission, (last_submission.c.student_id == ChallengeProgress.user_id) & (last_submission.c.challenge_id == ChallengeProgress.challenge_id)
        ).where(ChallengeProgress.user_id.in_(student_ids), ChallengeProgress.challenge_id.in_(challenge_ids), ChallengeProgress.completed_at.is_(None),
            func.coalesce(last_submission.c.last_attempt, ChallengeProgress.started_at) <= cutoff)
        stale_query = _apply_window(stale_query, ChallengeProgress.started_at, date_from, date_to).group_by(ChallengeProgress.challenge_id)
        abandoned_by_challenge = {int(row[0]): int(row[1] or 0) for row in db.execute(stale_query).all()}

    challenge_rows = []
    for item in challenges:
        started, completed = p_challenge.get(item.id, (0, 0))
        challenge_rows.append({"challenge_id": item.id, "title": item.title, "failures": f_challenge.get(item.id, 0),
            "started": started, "completed": completed, "abandoned": abandoned_by_challenge.get(item.id, 0)})
    challenging = sorted(challenge_rows, key=lambda row: (-cast(int, row["failures"]), -cast(int, row["abandoned"]), cast(str, row["title"])))[:10]
    mean_score = round(sum(row["score"] for row in student_rows) / len(student_rows), 2) if student_rows else 0
    score_rate_denominator = len(student_rows) * len(challenges)
    return {
        "scope": {"id": scope.resource_id, "name": scope.resource_name},
        "updated_at": now_utc(),
        "summary": {
            "students": len(students), "challenges": len(challenges), "started": total_started,
            "active": max(0, total_started - total_completed), "completed": total_completed,
            "flags_captured": total_completed, "attempts": total_attempts, "failed_attempts": total_failures,
            "hints": total_hints, "average_score": mean_score,
            "mean_completion_seconds": round(completion_duration_total / completion_duration_count) if completion_duration_count else 0,
            "completion_rate": round(total_completed / score_rate_denominator * 100, 1) if score_rate_denominator else 0,
            "abandoned": sum(item["abandoned"] for item in challenge_rows),
            "abandonment_threshold_days": ABANDONMENT_INACTIVITY_DAYS,
        },
        "students": student_rows, "challenging": challenging, "grade_scales": [
            {"id": row.id, "name": row.name} for row in db.scalars(select(GradeScale).order_by(GradeScale.name, GradeScale.id)).all()
        ],
    }


def live_class(db: Session, actor: User, *, class_id: int | None, event_id: int | None) -> dict[str, Any]:
    scope = resolve_scope(db, actor, class_id, event_id)
    student_ids = [row[0] for row in _students(db, scope, None)]
    if not student_ids or not scope.event_ids:
        return {"scope": {"id": scope.resource_id, "name": scope.resource_name}, "updated_at": now_utc(), "active": []}
    challenge_query = select(Challenge.id).where(Challenge.event_id.in_(scope.event_ids), Challenge.deleted_at.is_(None))
    active = db.execute(select(ChallengeProgress, Challenge.title, User.display_name).join(
        Challenge, Challenge.id == ChallengeProgress.challenge_id
    ).join(User, User.id == ChallengeProgress.user_id).where(
        ChallengeProgress.user_id.in_(student_ids), ChallengeProgress.challenge_id.in_(challenge_query), ChallengeProgress.completed_at.is_(None)
    ).order_by(ChallengeProgress.started_at.desc()).limit(500)).all()
    active_keys = {(row[0].user_id, row[0].challenge_id) for row in active}
    attempts = {(int(row[0]), int(row[1])): int(row[2]) for row in db.execute(select(
        ChallengeSubmission.user_id, ChallengeSubmission.challenge_id, func.count()
    ).where(ChallengeSubmission.user_id.in_(student_ids), ChallengeSubmission.challenge_id.in_(challenge_query)).group_by(
        ChallengeSubmission.user_id, ChallengeSubmission.challenge_id
    )).all()} if active_keys else {}
    hints = {(int(row[0]), int(row[1])): int(row[2]) for row in db.execute(select(
        HintUse.user_id, HintUse.challenge_id, func.count()
    ).where(HintUse.user_id.in_(student_ids), HintUse.challenge_id.in_(challenge_query)).group_by(
        HintUse.user_id, HintUse.challenge_id
    )).all()} if active_keys else {}
    scores = {(int(row[0]), int(row[1])): int(row[2] or 0) for row in db.execute(select(
        XpTransaction.user_id, XpTransaction.challenge_id, func.sum(XpTransaction.points)
    ).where(XpTransaction.user_id.in_(student_ids), XpTransaction.event_id.in_(scope.event_ids)).group_by(
        XpTransaction.user_id, XpTransaction.challenge_id
    )).all()} if active_keys else {}
    now = now_utc()
    rows = []
    for progress, title, student in active:
        elapsed = max(0, int((now - progress.started_at).total_seconds()) - progress.total_paused_seconds)
        if progress.paused_at is not None:
            elapsed = max(0, elapsed - int((now - progress.paused_at).total_seconds()))
        rows.append({"student_id": progress.user_id, "student": student, "challenge_id": progress.challenge_id,
            "challenge": title, "status": "PAUSED" if progress.paused_at else "IN_PROGRESS",
            "started_at": progress.started_at, "elapsed_seconds": elapsed,
            "attempts": attempts.get((progress.user_id, progress.challenge_id), 0),
            "hints": hints.get((progress.user_id, progress.challenge_id), 0),
            "score": scores.get((progress.user_id, progress.challenge_id), 0)})
    return {"scope": {"id": scope.resource_id, "name": scope.resource_name}, "updated_at": now, "active": rows}


def student_detail(db: Session, actor: User, *, student_id: int, class_id: int | None, event_id: int | None) -> dict[str, Any]:
    scope = resolve_scope(db, actor, class_id, event_id)
    if not any(item[0] == student_id for item in _students(db, scope, student_id)):
        raise HTTPException(404, "student not found")
    data = analytics(db, actor, class_id=class_id, event_id=event_id, student_id=student_id)
    summary = data["students"][0]
    history_rows = db.execute(select(XpTransaction, Challenge.title).join(
        Challenge, Challenge.id == XpTransaction.challenge_id
    ).where(XpTransaction.user_id == student_id, XpTransaction.event_id.in_(scope.event_ids)).order_by(
        XpTransaction.created_at.desc(), XpTransaction.id.desc()).limit(300)).all()
    failed_rows = db.execute(select(ChallengeSubmission.attempted_at, Challenge.title).join(
        Challenge, Challenge.id == ChallengeSubmission.challenge_id
    ).where(ChallengeSubmission.user_id == student_id, ChallengeSubmission.is_correct.is_(False),
        Challenge.event_id.in_(scope.event_ids)).order_by(ChallengeSubmission.attempted_at.desc()).limit(300)).all()
    category_rows = db.execute(select(Category.id, Category.name, func.count(ChallengeProgress.id),
        func.sum(case((ChallengeProgress.completed_at.is_not(None), 1), else_=0))).join(
        Challenge, Challenge.category_id == Category.id).join(ChallengeProgress, ChallengeProgress.challenge_id == Challenge.id).where(
        ChallengeProgress.user_id == student_id, Challenge.event_id.in_(scope.event_ids)
    ).group_by(Category.id, Category.name).order_by(Category.name)).all()
    history: list[dict[str, Any]] = [{"challenge": title, "type": row.source_type, "points": row.points, "created_at": row.created_at} for row, title in history_rows]
    history.extend({"challenge": title, "type": "FAILED_ATTEMPT", "points": 0, "created_at": at} for at, title in failed_rows)
    history.sort(key=lambda item: item["created_at"], reverse=True)
    return {"student": summary, "categories": [{"id": row[0], "name": row[1], "started": int(row[2] or 0), "completed": int(row[3] or 0)} for row in category_rows], "history": history[:300]}


def list_announcements(db: Session, actor: User, *, class_id: int | None, event_id: int | None, include_archived: bool) -> list[Announcement]:
    scope = resolve_scope(db, actor, class_id, event_id)
    predicates = [Announcement.class_id.in_(scope.class_ids)] if class_id is not None else [Announcement.event_id == event_id]
    query = select(Announcement).where(*predicates)
    if not include_archived:
        query = query.where(Announcement.archived_at.is_(None))
    return list(db.scalars(query.order_by(Announcement.publish_at.desc(), Announcement.id.desc())).all())


def student_announcements(db: Session, actor: User) -> list[Announcement]:
    if "STUDENT" not in user_roles(actor):
        raise HTTPException(403, "student role required")
    class_ids = select(class_students.c.class_id).where(class_students.c.student_user_id == actor.id)
    event_ids = select(ctf_event_classes.c.event_id).where(ctf_event_classes.c.class_id.in_(class_ids))
    return list(db.scalars(select(Announcement).where(Announcement.archived_at.is_(None), Announcement.publish_at <= now_utc(),
        (Announcement.class_id.in_(class_ids) | Announcement.event_id.in_(event_ids))
    ).order_by(Announcement.publish_at.desc()).limit(50)).all())


def create_announcement(db: Session, actor: User, *, class_id: int | None, event_id: int | None,
                         title: str, content_markdown: str, publish_at: datetime | None) -> Announcement:
    resolve_scope(db, actor, class_id, event_id)
    row = Announcement(author_user_id=actor.id, class_id=class_id, event_id=event_id,
        title=title.strip(), content_markdown=content_markdown.strip(), publish_at=_date_utc(publish_at) or now_utc())
    db.add(row)
    db.flush()
    return row


def archive_announcement(db: Session, actor: User, announcement: Announcement) -> None:
    resolve_scope(db, actor, announcement.class_id, announcement.event_id)
    announcement.archived_at = now_utc()


def close_event(db: Session, actor: User, event_id: int) -> CtfEvent:
    scope = resolve_scope(db, actor, None, event_id)
    event = db.get(CtfEvent, scope.resource_id)
    if event is None:
        raise HTTPException(404, "event not found")
    event.status = "ARCHIVED"
    event.ends_at = now_utc()
    db.flush()
    return event
