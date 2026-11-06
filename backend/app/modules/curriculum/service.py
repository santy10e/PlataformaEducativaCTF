"""Curriculum domain logic: authoring, learner access, progress and review (SPEC §3.1 items 3–5)."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import audit
from app.ctf_service import get_event, student_events
from app.events import event_bus
from app.models import (
    Category,
    Challenge,
    ChallengeProgress,
    Difficulty,
    Notification,
    SchoolClass,
    User,
    class_students,
)
from app.modules.curriculum.activity_types import REGISTRY, get_type
from app.modules.curriculum.models import (
    COURSE_STATUSES,
    Activity,
    ActivityHint,
    ActivityProgress,
    Course,
    CourseModule,
    HintUsage,
    Lesson,
)
from app.users_service import user_roles

REVIEW_DECISIONS = {"APPROVED", "REJECTED", "NEEDS_CHANGES"}


def now_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def is_admin(actor: User) -> bool:
    return "ADMIN" in user_roles(actor)


def _status(value: str) -> str:
    if value not in COURSE_STATUSES:
        raise ValueError("status must be DRAFT, PUBLISHED or ARCHIVED")
    return value


# ---------------------------------------------------------------- staff scope

def can_manage(actor: User, course: Course) -> bool:
    """Admins manage everything; instructors manage the courses they own. Shared templates (no owner) are admin-only."""
    return is_admin(actor) or (course.owner_user_id is not None and course.owner_user_id == actor.id)


def staff_courses(db: Session, actor: User) -> list[Course]:
    query = select(Course).options(selectinload(Course.classes)).where(Course.deleted_at.is_(None))
    if not is_admin(actor):
        query = query.where((Course.owner_user_id == actor.id) | Course.owner_user_id.is_(None))
    return list(db.scalars(query.order_by(Course.title, Course.id)).all())


def staff_course(db: Session, actor: User, course_id: int, *, manage: bool = False) -> Course:
    course = db.get(Course, course_id)
    if course is None or course.deleted_at is not None:
        raise LookupError("course not found")
    readable = is_admin(actor) or course.owner_user_id in (None, actor.id)
    if not readable or (manage and not can_manage(actor, course)):
        raise LookupError("course not found")
    return course


def staff_module(db: Session, actor: User, module_id: int) -> CourseModule:
    module = db.get(CourseModule, module_id)
    if module is None or module.deleted_at is not None:
        raise LookupError("module not found")
    staff_course(db, actor, module.course_id, manage=True)
    return module


def staff_lesson(db: Session, actor: User, lesson_id: int) -> Lesson:
    lesson = db.get(Lesson, lesson_id)
    if lesson is None or lesson.deleted_at is not None:
        raise LookupError("lesson not found")
    staff_module(db, actor, lesson.module_id)
    return lesson


def staff_activity(db: Session, actor: User, activity_id: int, *, manage: bool = True) -> Activity:
    activity = db.get(Activity, activity_id)
    if activity is None or activity.deleted_at is not None:
        raise LookupError("activity not found")
    staff_course(db, actor, course_of(activity).id, manage=manage)
    return activity


def course_of(activity: Activity) -> Course:
    return activity.lesson.module.course


# ---------------------------------------------------------------- authoring

def save_course(db: Session, actor: User, course: Course | None, *, title: str, description_markdown: str, status: str) -> Course:
    if course is None:
        course = Course(public_id=str(uuid4()), owner_user_id=actor.id)
        db.add(course)
    course.title = title.strip()
    course.description_markdown = description_markdown
    course.status = _status(status)
    db.flush()
    return course


def assign_classes(db: Session, actor: User, course: Course, class_ids: list[int]) -> None:
    if len(set(class_ids)) != len(class_ids):
        raise ValueError("duplicate class id")
    classes = list(db.scalars(select(SchoolClass).where(SchoolClass.id.in_(class_ids))).all()) if class_ids else []
    if len(classes) != len(class_ids):
        raise ValueError("one or more classes were not found")
    if not is_admin(actor):
        if any(item.teacher_user_id != actor.id for item in classes):
            raise PermissionError("you can only assign classes you teach")
        # Classes of other teachers already on the course are not the actor's to remove.
        classes = [item for item in course.classes if item.teacher_user_id != actor.id] + classes
    course.classes = classes
    db.flush()


def save_module(db: Session, course: Course, module: CourseModule | None, *, title: str, description_markdown: str, sort_order: int, status: str) -> CourseModule:
    if module is None:
        module = CourseModule(public_id=str(uuid4()), course_id=course.id)
        db.add(module)
    module.title, module.description_markdown, module.sort_order, module.status = title.strip(), description_markdown, sort_order, _status(status)
    db.flush()
    return module


def save_lesson(db: Session, module: CourseModule, lesson: Lesson | None, *, title: str, content_markdown: str, estimated_minutes: int | None, sort_order: int, status: str) -> Lesson:
    if lesson is None:
        lesson = Lesson(public_id=str(uuid4()), module_id=module.id)
        db.add(lesson)
    lesson.title, lesson.content_markdown, lesson.estimated_minutes = title.strip(), content_markdown, estimated_minutes
    lesson.sort_order, lesson.status = sort_order, _status(status)
    db.flush()
    return lesson


def _course_activities(db: Session, course_id: int) -> list[Activity]:
    return list(db.scalars(
        select(Activity).join(Lesson).join(CourseModule)
        .options(selectinload(Activity.prerequisites))
        .where(CourseModule.course_id == course_id, Activity.deleted_at.is_(None))
    ).all())


def _check_prerequisites(db: Session, course_id: int, activity_id: int | None, prerequisite_ids: list[int]) -> list[Activity]:
    if len(set(prerequisite_ids)) != len(prerequisite_ids):
        raise ValueError("duplicate prerequisites are not allowed")
    if activity_id is not None and activity_id in prerequisite_ids:
        raise ValueError("an activity cannot require itself")
    same_course = {item.id: item for item in _course_activities(db, course_id)}
    required = [same_course[i] for i in prerequisite_ids if i in same_course]
    if len(required) != len(prerequisite_ids):
        raise ValueError("prerequisites must be activities of the same course")
    if activity_id is not None:
        graph = {item.id: [parent.id for parent in item.prerequisites] for item in same_course.values()}
        graph[activity_id] = list(prerequisite_ids)

        def reaches(node: int, seen: set[int]) -> bool:
            if node == activity_id:
                return True
            if node in seen:
                return False
            seen.add(node)
            return any(reaches(parent, seen) for parent in graph.get(node, []))

        if any(reaches(item, set()) for item in prerequisite_ids):
            raise ValueError("activity prerequisites cannot contain cycles")
    return required


def _validate_ctf_reference(db: Session, actor: User, config: dict[str, Any]) -> None:
    challenge = db.get(Challenge, config["challenge_id"])
    if challenge is None or challenge.deleted_at is not None or get_event(db, actor, challenge.event_id) is None:
        raise ValueError("the referenced CTF challenge does not exist or is not yours")


def save_activity(db: Session, actor: User, lesson: Lesson, activity: Activity | None, *, type: str, title: str, description_markdown: str,
                  sort_order: int, category_id: int | None, difficulty_id: int | None, points: int, xp: int, status: str,
                  config: dict[str, Any], prerequisite_ids: list[int]) -> Activity:
    kind = get_type(type)
    if activity is not None and activity.type != type:
        raise ValueError("the activity type cannot change; create a new activity instead")
    clean = kind.validate_config(config)
    if category_id is not None and db.get(Category, category_id) is None:
        raise ValueError("category not found")
    if difficulty_id is not None and db.get(Difficulty, difficulty_id) is None:
        raise ValueError("difficulty not found")
    if type == "ctf_challenge":
        _validate_ctf_reference(db, actor, clean)
    course_id = lesson.module.course_id
    if activity is None:
        activity = Activity(public_id=str(uuid4()), lesson_id=lesson.id, type=type)
        db.add(activity)
    activity.title, activity.description_markdown, activity.sort_order = title.strip(), description_markdown, sort_order
    activity.category_id, activity.difficulty_id, activity.points, activity.xp = category_id, difficulty_id, points, xp
    activity.status, activity.config = _status(status), clean
    db.flush()  # a new activity needs its id before the prerequisite graph is checked
    activity.prerequisites = _check_prerequisites(db, course_id, activity.id, prerequisite_ids)
    db.flush()
    return activity


def save_hint(db: Session, activity: Activity, hint: ActivityHint | None, *, order: int, cost: int, content_markdown: str) -> ActivityHint:
    clash = db.scalar(select(ActivityHint.id).where(ActivityHint.activity_id == activity.id, ActivityHint.order == order, ActivityHint.id != (hint.id if hint else -1)))
    if clash is not None:
        raise ValueError("hint order already exists")
    if hint is None:
        hint = ActivityHint(activity_id=activity.id)
        db.add(hint)
    hint.order, hint.cost, hint.content_markdown = order, cost, content_markdown
    db.flush()
    return hint


def soft_delete(item: Course | CourseModule | Lesson | Activity) -> None:
    item.deleted_at = now_utc()
    item.status = "ARCHIVED"


def duplicate_course(db: Session, actor: User, source: Course) -> Course:
    """Copies a course (for example the shared 9-month plan) into a draft owned by the actor."""
    copy = Course(public_id=str(uuid4()), owner_user_id=actor.id, title=f"{source.title} (copia)"[:160], description_markdown=source.description_markdown, status="DRAFT")
    db.add(copy)
    db.flush()
    mapping: dict[int, Activity] = {}
    originals: list[Activity] = []
    for module in live(source.modules):
        new_module = CourseModule(public_id=str(uuid4()), course_id=copy.id, title=module.title, description_markdown=module.description_markdown, sort_order=module.sort_order, status=module.status)
        db.add(new_module)
        db.flush()
        for lesson in live(module.lessons):
            new_lesson = Lesson(public_id=str(uuid4()), module_id=new_module.id, title=lesson.title, content_markdown=lesson.content_markdown, estimated_minutes=lesson.estimated_minutes, sort_order=lesson.sort_order, status=lesson.status)
            db.add(new_lesson)
            db.flush()
            for activity in live(lesson.activities):
                clone = Activity(public_id=str(uuid4()), lesson_id=new_lesson.id, type=activity.type, title=activity.title, description_markdown=activity.description_markdown,
                                 sort_order=activity.sort_order, category_id=activity.category_id, difficulty_id=activity.difficulty_id, points=activity.points, xp=activity.xp,
                                 status=activity.status, config=dict(activity.config))
                clone.hints = [ActivityHint(order=h.order, cost=h.cost, content_markdown=h.content_markdown) for h in activity.hints]
                db.add(clone)
                mapping[activity.id] = clone
                originals.append(activity)
    db.flush()
    for activity in originals:
        mapping[activity.id].prerequisites = [mapping[p.id] for p in activity.prerequisites if p.id in mapping]
    db.flush()
    return copy


def live[T: (CourseModule, Lesson, Activity)](items: list[T]) -> list[T]:
    return [item for item in items if item.deleted_at is None]


# ---------------------------------------------------------------- learner access

def learner_courses(db: Session, user: User) -> list[Course]:
    class_ids = [item.id for item in user.enrolled_classes]
    if not class_ids:
        return []
    from app.modules.curriculum.models import course_classes

    assigned = select(course_classes.c.course_id).where(course_classes.c.class_id.in_(class_ids))
    return list(db.scalars(select(Course).where(Course.id.in_(assigned), Course.status == "PUBLISHED", Course.deleted_at.is_(None)).order_by(Course.title)).all())


def published(items: list[Any]) -> list[Any]:
    return [item for item in items if item.deleted_at is None and item.status == "PUBLISHED"]


def learner_course(db: Session, user: User, public_id: str) -> Course:
    course = next((item for item in learner_courses(db, user) if item.public_id == public_id), None)
    if course is None:
        raise LookupError("course not found")
    return course


def learner_activity(db: Session, user: User, public_id: str) -> Activity:
    activity = db.scalar(select(Activity).where(Activity.public_id == public_id))
    if activity is None or activity.deleted_at is not None or activity.status != "PUBLISHED":
        raise LookupError("activity not found")
    lesson, module, course = activity.lesson, activity.lesson.module, activity.lesson.module.course
    if not all(item.deleted_at is None and item.status == "PUBLISHED" for item in (lesson, module)):
        raise LookupError("activity not found")
    if course.id not in {item.id for item in learner_courses(db, user)}:
        raise LookupError("activity not found")
    return activity


def _ctf_state(db: Session, user: User, activity: Activity) -> tuple[str, Challenge | None]:
    challenge = db.get(Challenge, activity.config.get("challenge_id"))
    if challenge is None or challenge.deleted_at is not None or challenge.status != "PUBLISHED" or challenge.event not in student_events(db, user):
        return "UNAVAILABLE", None
    row = db.scalar(select(ChallengeProgress).where(ChallengeProgress.user_id == user.id, ChallengeProgress.challenge_id == challenge.id))
    if row is None:
        return "NOT_STARTED", challenge
    return ("APPROVED" if row.completed_at is not None else "IN_PROGRESS"), challenge


def progress_row(db: Session, user: User, activity: Activity) -> ActivityProgress | None:
    return db.scalar(select(ActivityProgress).where(ActivityProgress.user_id == user.id, ActivityProgress.activity_id == activity.id))


def status_of(db: Session, user: User, activity: Activity) -> str:
    if activity.type == "ctf_challenge":
        return _ctf_state(db, user, activity)[0]
    row = progress_row(db, user, activity)
    return row.status if row else "NOT_STARTED"


def blocked_by(db: Session, user: User, activity: Activity) -> list[Activity]:
    return [item for item in activity.prerequisites if item.deleted_at is None and status_of(db, user, item) != "APPROVED"]


def learner_view(db: Session, user: User, activity: Activity) -> dict[str, Any]:
    """The only representation of an activity a learner ever receives (no answers, no locked hints)."""
    kind = get_type(activity.type)
    locks = blocked_by(db, user, activity)
    row = progress_row(db, user, activity)
    used = set(db.scalars(select(HintUsage.hint_id).where(HintUsage.user_id == user.id, HintUsage.activity_id == activity.id)).all())
    view: dict[str, Any] = {
        "public_id": activity.public_id, "type": activity.type, "type_label": kind.label, "title": activity.title,
        "description_markdown": "" if locks else activity.description_markdown, "points": activity.points, "xp": activity.xp,
        "category": activity.category.name if activity.category else None, "difficulty": activity.difficulty.name if activity.difficulty else None,
        "locked": bool(locks), "lock_reason": ("Completa primero: " + ", ".join(item.title for item in locks)) if locks else None,
        "config": {} if locks else kind.student_config(activity.config),
        "status": status_of(db, user, activity), "score": row.score if row else None, "max_score": row.max_score if row else None,
        "attempts": row.attempts if row else 0, "feedback": row.feedback if row else "",
        "submission": row.submission if row else {},
        "hints": [] if locks else [
            {"id": hint.id, "order": hint.order, "cost": hint.cost, "unlocked": hint.id in used, "content_markdown": hint.content_markdown if hint.id in used else None}
            for hint in activity.hints
        ],
        "ctf": None,
    }
    if activity.type == "ctf_challenge" and not locks:
        state, challenge = _ctf_state(db, user, activity)
        view["ctf"] = {"available": challenge is not None, "event_public_id": challenge.event.public_id if challenge else None,
                       "challenge_public_id": challenge.public_id if challenge else None, "state": state}
    return view


def course_outline(db: Session, user: User, course: Course) -> dict[str, Any]:
    modules = []
    for module in published(course.modules):
        lessons = []
        for lesson in published(module.lessons):
            activities = [{"public_id": a.public_id, "title": a.title, "type": a.type, "status": status_of(db, user, a), "locked": bool(blocked_by(db, user, a))} for a in published(lesson.activities)]
            lessons.append({"public_id": lesson.public_id, "title": lesson.title, "estimated_minutes": lesson.estimated_minutes, "activities": activities})
        total = sum(len(lesson["activities"]) for lesson in lessons)
        done = sum(1 for lesson in lessons for a in lesson["activities"] if a["status"] == "APPROVED")
        modules.append({"public_id": module.public_id, "title": module.title, "description_markdown": module.description_markdown, "lessons": lessons,
                        "completed": done, "total": total})
    return {"public_id": course.public_id, "title": course.title, "description_markdown": course.description_markdown, "modules": modules}


def learner_lesson(db: Session, user: User, public_id: str) -> dict[str, Any]:
    lesson = db.scalar(select(Lesson).where(Lesson.public_id == public_id))
    if lesson is None or lesson.deleted_at is not None or lesson.status != "PUBLISHED" or lesson.module.deleted_at is not None or lesson.module.status != "PUBLISHED":
        raise LookupError("lesson not found")
    course = lesson.module.course
    if course.id not in {item.id for item in learner_courses(db, user)}:
        raise LookupError("lesson not found")
    return {"public_id": lesson.public_id, "title": lesson.title, "content_markdown": lesson.content_markdown, "estimated_minutes": lesson.estimated_minutes,
            "module": {"public_id": lesson.module.public_id, "title": lesson.module.title}, "course": {"public_id": course.public_id, "title": course.title},
            "activities": [learner_view(db, user, activity) for activity in published(lesson.activities)]}


def _ensure_row(db: Session, user: User, activity: Activity) -> ActivityProgress:
    row = progress_row(db, user, activity)
    if row is None:
        row = ActivityProgress(user_id=user.id, activity_id=activity.id, status="IN_PROGRESS", started_at=now_utc(), submission={})
        db.add(row)
        db.flush()
    return row


def start(db: Session, user: User, activity: Activity) -> ActivityProgress:
    if activity.type == "ctf_challenge":
        raise ValueError("CTF challenges are started from the challenge itself")
    if blocked_by(db, user, activity):
        raise PermissionError("complete the prerequisites first")
    return _ensure_row(db, user, activity)


def submit(db: Session, user: User, activity: Activity, payload: dict[str, Any]) -> dict[str, Any]:
    kind = get_type(activity.type)
    if not kind.submittable:
        raise ValueError("this activity is completed elsewhere")
    if blocked_by(db, user, activity):
        raise PermissionError("complete the prerequisites first")
    row = _ensure_row(db, user, activity)
    # NEEDS_CHANGES and REJECTED submissions may be sent again; a pending one may not.
    if row.status == "PENDING_REVIEW":
        raise ValueError("your previous submission is waiting for review")
    if row.status == "APPROVED" and activity.type != "quiz":
        raise ValueError("this activity is already approved")
    limit = activity.config.get("max_attempts")
    if limit is not None and row.attempts >= int(limit):
        raise PermissionError("attempt limit reached")
    outcome = kind.grade(activity.config, activity.points, payload)
    row.attempts += 1
    row.submitted_at = now_utc()
    row.submission = payload
    row.auto_graded = outcome.auto_graded
    row.max_score = outcome.max_score
    row.feedback = outcome.feedback
    if outcome.status == "APPROVED":
        # Retrying a quiz keeps the best result.
        row.score = max(outcome.score or 0, row.score or 0) if row.status == "APPROVED" else outcome.score
        row.completed_at = row.completed_at or now_utc()
    row.status = "APPROVED" if row.status == "APPROVED" else outcome.status
    audit.log(db, "ACTIVITY_SUBMITTED", user.id, "activity", activity.public_id, {"status": row.status, "attempt": row.attempts})
    event_bus.publish("activity_submitted", {"user_id": user.id, "activity_id": activity.id, "status": row.status})
    db.flush()
    return {"status": row.status, "score": row.score, "max_score": row.max_score, "feedback": row.feedback, "attempts": row.attempts, "details": outcome.details}


def use_hint(db: Session, user: User, activity: Activity, hint_id: int) -> ActivityHint:
    if blocked_by(db, user, activity):
        raise PermissionError("complete the prerequisites first")
    used = set(db.scalars(select(HintUsage.hint_id).where(HintUsage.user_id == user.id, HintUsage.activity_id == activity.id)).all())
    next_hint = next((hint for hint in activity.hints if hint.id not in used), None)
    if next_hint is None or next_hint.id != hint_id:
        raise ValueError("hints must be unlocked in order")
    _ensure_row(db, user, activity)
    # TODO(fase-6): the hint cost is recorded here and deducted by the SPEC §7.1 scoring strategy.
    db.add(HintUsage(user_id=user.id, activity_id=activity.id, hint_id=next_hint.id, cost=next_hint.cost))
    audit.log(db, "ACTIVITY_HINT_USED", user.id, "activity", activity.public_id, {"hint_order": next_hint.order, "cost": next_hint.cost})
    event_bus.publish("hint_used", {"user_id": user.id, "activity_id": activity.id, "hint_id": next_hint.id, "cost": next_hint.cost})
    db.flush()
    return next_hint


# ---------------------------------------------------------------- review and progress (staff)

def review_queue(db: Session, actor: User, status: str = "PENDING_REVIEW") -> list[ActivityProgress]:
    query = (select(ActivityProgress).join(Activity).join(Lesson).join(CourseModule).join(Course)
             .options(selectinload(ActivityProgress.activity), selectinload(ActivityProgress.user))
             .where(ActivityProgress.status == status, Activity.deleted_at.is_(None), Course.deleted_at.is_(None)))
    if not is_admin(actor):
        query = query.where(Course.owner_user_id == actor.id)
    return list(db.scalars(query.order_by(ActivityProgress.submitted_at, ActivityProgress.id)).all())


def review(db: Session, actor: User, progress_id: int, *, decision: str, score: int | None, feedback: str) -> ActivityProgress:
    row = db.get(ActivityProgress, progress_id)
    if row is None or not can_manage(actor, course_of(row.activity)):
        raise LookupError("submission not found")
    if row.status != "PENDING_REVIEW":
        raise ValueError("only pending submissions can be reviewed")
    if decision not in REVIEW_DECISIONS:
        raise ValueError("decision must be APPROVED, REJECTED or NEEDS_CHANGES")
    if decision == "APPROVED":
        if score is None or not 0 <= score <= row.activity.points:
            raise ValueError(f"score must be between 0 and {row.activity.points}")
        row.score, row.completed_at = score, now_utc()
    elif not feedback.strip():
        raise ValueError("explain what to change or why it was rejected")
    row.status, row.feedback = decision, feedback.strip()
    row.reviewed_by_user_id, row.reviewed_at = actor.id, now_utc()
    db.add(Notification(user_id=row.user_id, event_type="ACTIVITY_REVIEWED", payload={"activity_public_id": row.activity.public_id, "decision": decision}, created_at=now_utc()))
    audit.log(db, "ACTIVITY_REVIEWED", actor.id, "activity_progress", str(row.id), {"decision": decision, "score": row.score})
    if decision == "APPROVED":
        event_bus.publish("activity_approved", {"user_id": row.user_id, "activity_id": row.activity_id, "score": row.score})
    db.flush()
    return row


def course_progress(db: Session, actor: User, course: Course) -> dict[str, Any]:
    """Completion per student and module for the classes the actor may see (SPEC §3.1 item 5)."""
    class_ids = [item.id for item in course.classes if is_admin(actor) or item.teacher_user_id == actor.id]
    students = list(db.scalars(select(User).join(class_students, class_students.c.student_user_id == User.id)
                               .where(class_students.c.class_id.in_(class_ids), User.is_active.is_(True)).distinct().order_by(User.display_name)).all()) if class_ids else []
    modules = [(module, [a for lesson in published(module.lessons) for a in published(lesson.activities)]) for module in published(course.modules)]
    rows = []
    for student in students:
        cells = []
        for module, activities in modules:
            done = sum(1 for activity in activities if status_of(db, student, activity) == "APPROVED")
            cells.append({"module_public_id": module.public_id, "completed": done, "total": len(activities)})
        pending = db.scalar(select(ActivityProgress.id).where(ActivityProgress.user_id == student.id, ActivityProgress.status == "PENDING_REVIEW",
                                                             ActivityProgress.activity_id.in_([a.id for _, acts in modules for a in acts] or [-1])).limit(1))
        rows.append({"student_id": student.id, "display_name": student.display_name, "modules": cells, "pending_review": pending is not None})
    return {"modules": [{"public_id": m.public_id, "title": m.title} for m, _ in modules], "students": rows}


def activity_types() -> list[dict[str, Any]]:
    return [{"key": kind.key, "label": kind.label, "submittable": kind.submittable} for kind in REGISTRY.values()]
