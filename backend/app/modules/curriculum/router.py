"""HTTP layer for the curriculum: translates domain errors to status codes and audits; no business rules."""

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import audit
from app.dependencies import get_db, require_csrf, require_permission
from app.models import User
from app.modules.curriculum import service
from app.modules.curriculum.models import Activity, ActivityHint, Course, CourseModule, Lesson
from app.modules.curriculum.permissions import (
    ACTIVITY_REVIEW,
    ACTIVITY_SUBMIT,
    COURSE_MANAGE,
    COURSE_VIEW,
)
from app.modules.curriculum.schemas import (
    ActivityInput,
    CourseClassesInput,
    CourseInput,
    HintInput,
    LearnerActivity,
    LearnerLesson,
    LearnerSubmissionResult,
    LessonInput,
    ModuleInput,
    ReviewInput,
    SubmissionInput,
)
from app.users_service import user_roles

staff = APIRouter(prefix="/api/v1/curriculum", tags=["curriculum"])
learn = APIRouter(prefix="/api/v1/learn", tags=["learn"])


def run[T](action: Callable[[], T]) -> T:
    try:
        return action()
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def _learner(actor: User) -> None:
    if "STUDENT" not in user_roles(actor):
        raise HTTPException(403, "student role required")


# ---------------------------------------------------------------- staff serializers

def _hint(item: ActivityHint) -> dict[str, Any]:
    return {"id": item.id, "order": item.order, "cost": item.cost, "content_markdown": item.content_markdown}


def _activity(item: Activity) -> dict[str, Any]:
    return {"id": item.id, "public_id": item.public_id, "lesson_id": item.lesson_id, "type": item.type, "title": item.title,
            "description_markdown": item.description_markdown, "sort_order": item.sort_order, "category_id": item.category_id,
            "difficulty_id": item.difficulty_id, "points": item.points, "xp": item.xp, "status": item.status, "config": item.config,
            "prerequisite_ids": [p.id for p in item.prerequisites if p.deleted_at is None], "hints": [_hint(h) for h in item.hints]}


def _lesson(item: Lesson) -> dict[str, Any]:
    return {"id": item.id, "public_id": item.public_id, "module_id": item.module_id, "title": item.title, "content_markdown": item.content_markdown,
            "estimated_minutes": item.estimated_minutes, "sort_order": item.sort_order, "status": item.status,
            "activities": [_activity(a) for a in service.live(item.activities)]}


def _module(item: CourseModule) -> dict[str, Any]:
    return {"id": item.id, "public_id": item.public_id, "course_id": item.course_id, "title": item.title, "description_markdown": item.description_markdown,
            "sort_order": item.sort_order, "status": item.status, "lessons": [_lesson(lesson) for lesson in service.live(item.lessons)]}


def _course(item: Course, actor: User, *, tree: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {"id": item.id, "public_id": item.public_id, "title": item.title, "description_markdown": item.description_markdown,
                            "status": item.status, "owner_user_id": item.owner_user_id, "is_template": item.owner_user_id is None,
                            "can_manage": service.can_manage(actor, item), "class_ids": [c.id for c in item.classes],
                            "class_names": [c.name for c in item.classes], "module_count": len(service.live(item.modules))}
    if tree:
        data["modules"] = [_module(module) for module in service.live(item.modules)]
    return data


# ---------------------------------------------------------------- staff: courses

@staff.get("/activity-types")
def activity_types(actor: User = Depends(require_permission(COURSE_VIEW))) -> list[dict[str, Any]]:
    return service.activity_types()


@staff.get("/courses")
def list_courses(actor: User = Depends(require_permission(COURSE_MANAGE)), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [_course(item, actor) for item in service.staff_courses(db, actor)]


@staff.post("/courses", dependencies=[Depends(require_csrf)])
def create_course(payload: CourseInput, actor: User = Depends(require_permission(COURSE_MANAGE)), db: Session = Depends(get_db)) -> dict[str, Any]:
    item = run(lambda: service.save_course(db, actor, None, **payload.model_dump()))
    audit.log(db, "COURSE_CREATED", actor.id, "course", item.public_id)
    db.commit()
    return _course(item, actor, tree=True)


@staff.get("/courses/{course_id}")
def get_course(course_id: int, actor: User = Depends(require_permission(COURSE_MANAGE)), db: Session = Depends(get_db)) -> dict[str, Any]:
    return _course(run(lambda: service.staff_course(db, actor, course_id)), actor, tree=True)


@staff.put("/courses/{course_id}", dependencies=[Depends(require_csrf)])
def update_course(course_id: int, payload: CourseInput, actor: User = Depends(require_permission(COURSE_MANAGE)), db: Session = Depends(get_db)) -> dict[str, Any]:
    course = run(lambda: service.staff_course(db, actor, course_id, manage=True))
    run(lambda: service.save_course(db, actor, course, **payload.model_dump()))
    audit.log(db, "COURSE_MODIFIED", actor.id, "course", course.public_id)
    db.commit()
    return _course(course, actor, tree=True)


@staff.delete("/courses/{course_id}", dependencies=[Depends(require_csrf)])
def delete_course(course_id: int, actor: User = Depends(require_permission(COURSE_MANAGE)), db: Session = Depends(get_db)) -> dict[str, bool]:
    course = run(lambda: service.staff_course(db, actor, course_id, manage=True))
    service.soft_delete(course)
    audit.log(db, "COURSE_ARCHIVED", actor.id, "course", course.public_id)
    db.commit()
    return {"ok": True}


@staff.post("/courses/{course_id}/duplicate", dependencies=[Depends(require_csrf)])
def duplicate_course(course_id: int, actor: User = Depends(require_permission(COURSE_MANAGE)), db: Session = Depends(get_db)) -> dict[str, Any]:
    source = run(lambda: service.staff_course(db, actor, course_id))
    copy = service.duplicate_course(db, actor, source)
    audit.log(db, "COURSE_DUPLICATED", actor.id, "course", copy.public_id, {"source": source.public_id})
    db.commit()
    return _course(copy, actor, tree=True)


@staff.put("/courses/{course_id}/classes", dependencies=[Depends(require_csrf)])
def set_course_classes(course_id: int, payload: CourseClassesInput, actor: User = Depends(require_permission(COURSE_MANAGE)), db: Session = Depends(get_db)) -> dict[str, Any]:
    course = run(lambda: service.staff_course(db, actor, course_id, manage=True))
    run(lambda: service.assign_classes(db, actor, course, payload.class_ids))
    audit.log(db, "COURSE_CLASSES_MODIFIED", actor.id, "course", course.public_id, {"class_ids": [c.id for c in course.classes]})
    db.commit()
    return _course(course, actor)


@staff.get("/courses/{course_id}/progress")
def get_course_progress(course_id: int, actor: User = Depends(require_permission(COURSE_MANAGE)), db: Session = Depends(get_db)) -> dict[str, Any]:
    course = run(lambda: service.staff_course(db, actor, course_id))
    return service.course_progress(db, actor, course)


# ---------------------------------------------------------------- staff: modules, lessons, activities, hints

@staff.post("/courses/{course_id}/modules", dependencies=[Depends(require_csrf)])
def create_module(course_id: int, payload: ModuleInput, actor: User = Depends(require_permission(COURSE_MANAGE)), db: Session = Depends(get_db)) -> dict[str, Any]:
    course = run(lambda: service.staff_course(db, actor, course_id, manage=True))
    item = run(lambda: service.save_module(db, course, None, **payload.model_dump()))
    audit.log(db, "MODULE_CREATED", actor.id, "module", item.public_id)
    db.commit()
    return _module(item)


@staff.put("/modules/{module_id}", dependencies=[Depends(require_csrf)])
def update_module(module_id: int, payload: ModuleInput, actor: User = Depends(require_permission(COURSE_MANAGE)), db: Session = Depends(get_db)) -> dict[str, Any]:
    item = run(lambda: service.staff_module(db, actor, module_id))
    run(lambda: service.save_module(db, item.course, item, **payload.model_dump()))
    audit.log(db, "MODULE_MODIFIED", actor.id, "module", item.public_id)
    db.commit()
    return _module(item)


@staff.delete("/modules/{module_id}", dependencies=[Depends(require_csrf)])
def delete_module(module_id: int, actor: User = Depends(require_permission(COURSE_MANAGE)), db: Session = Depends(get_db)) -> dict[str, bool]:
    item = run(lambda: service.staff_module(db, actor, module_id))
    service.soft_delete(item)
    audit.log(db, "MODULE_ARCHIVED", actor.id, "module", item.public_id)
    db.commit()
    return {"ok": True}


@staff.post("/modules/{module_id}/lessons", dependencies=[Depends(require_csrf)])
def create_lesson(module_id: int, payload: LessonInput, actor: User = Depends(require_permission(COURSE_MANAGE)), db: Session = Depends(get_db)) -> dict[str, Any]:
    module = run(lambda: service.staff_module(db, actor, module_id))
    item = run(lambda: service.save_lesson(db, module, None, **payload.model_dump()))
    audit.log(db, "LESSON_CREATED", actor.id, "lesson", item.public_id)
    db.commit()
    return _lesson(item)


@staff.put("/lessons/{lesson_id}", dependencies=[Depends(require_csrf)])
def update_lesson(lesson_id: int, payload: LessonInput, actor: User = Depends(require_permission(COURSE_MANAGE)), db: Session = Depends(get_db)) -> dict[str, Any]:
    item = run(lambda: service.staff_lesson(db, actor, lesson_id))
    run(lambda: service.save_lesson(db, item.module, item, **payload.model_dump()))
    audit.log(db, "LESSON_MODIFIED", actor.id, "lesson", item.public_id)
    db.commit()
    return _lesson(item)


@staff.delete("/lessons/{lesson_id}", dependencies=[Depends(require_csrf)])
def delete_lesson(lesson_id: int, actor: User = Depends(require_permission(COURSE_MANAGE)), db: Session = Depends(get_db)) -> dict[str, bool]:
    item = run(lambda: service.staff_lesson(db, actor, lesson_id))
    service.soft_delete(item)
    audit.log(db, "LESSON_ARCHIVED", actor.id, "lesson", item.public_id)
    db.commit()
    return {"ok": True}


@staff.post("/lessons/{lesson_id}/activities", dependencies=[Depends(require_csrf)])
def create_activity(lesson_id: int, payload: ActivityInput, actor: User = Depends(require_permission(COURSE_MANAGE)), db: Session = Depends(get_db)) -> dict[str, Any]:
    lesson = run(lambda: service.staff_lesson(db, actor, lesson_id))
    try:
        item = run(lambda: service.save_activity(db, actor, lesson, None, **payload.model_dump()))
    except HTTPException:
        db.rollback()
        raise
    audit.log(db, "ACTIVITY_CREATED", actor.id, "activity", item.public_id, {"type": item.type})
    db.commit()
    return _activity(item)


@staff.get("/activities/{activity_id}")
def get_activity(activity_id: int, actor: User = Depends(require_permission(COURSE_MANAGE)), db: Session = Depends(get_db)) -> dict[str, Any]:
    return _activity(run(lambda: service.staff_activity(db, actor, activity_id, manage=False)))


@staff.put("/activities/{activity_id}", dependencies=[Depends(require_csrf)])
def update_activity(activity_id: int, payload: ActivityInput, actor: User = Depends(require_permission(COURSE_MANAGE)), db: Session = Depends(get_db)) -> dict[str, Any]:
    item = run(lambda: service.staff_activity(db, actor, activity_id))
    try:
        run(lambda: service.save_activity(db, actor, item.lesson, item, **payload.model_dump()))
    except HTTPException:
        db.rollback()
        raise
    audit.log(db, "ACTIVITY_MODIFIED", actor.id, "activity", item.public_id)
    db.commit()
    return _activity(item)


@staff.delete("/activities/{activity_id}", dependencies=[Depends(require_csrf)])
def delete_activity(activity_id: int, actor: User = Depends(require_permission(COURSE_MANAGE)), db: Session = Depends(get_db)) -> dict[str, bool]:
    item = run(lambda: service.staff_activity(db, actor, activity_id))
    service.soft_delete(item)
    audit.log(db, "ACTIVITY_ARCHIVED", actor.id, "activity", item.public_id)
    db.commit()
    return {"ok": True}


@staff.post("/activities/{activity_id}/hints", dependencies=[Depends(require_csrf)])
def create_hint(activity_id: int, payload: HintInput, actor: User = Depends(require_permission(COURSE_MANAGE)), db: Session = Depends(get_db)) -> dict[str, Any]:
    activity = run(lambda: service.staff_activity(db, actor, activity_id))
    hint = run(lambda: service.save_hint(db, activity, None, **payload.model_dump()))
    audit.log(db, "ACTIVITY_HINT_CREATED", actor.id, "activity", activity.public_id, {"order": hint.order})
    db.commit()
    return _hint(hint)


@staff.put("/activities/{activity_id}/hints/{hint_id}", dependencies=[Depends(require_csrf)])
def update_hint(activity_id: int, hint_id: int, payload: HintInput, actor: User = Depends(require_permission(COURSE_MANAGE)), db: Session = Depends(get_db)) -> dict[str, Any]:
    activity = run(lambda: service.staff_activity(db, actor, activity_id))
    hint = next((h for h in activity.hints if h.id == hint_id), None)
    if hint is None:
        raise HTTPException(404, "hint not found")
    run(lambda: service.save_hint(db, activity, hint, **payload.model_dump()))
    audit.log(db, "ACTIVITY_HINT_MODIFIED", actor.id, "activity", activity.public_id, {"order": hint.order})
    db.commit()
    return _hint(hint)


@staff.delete("/activities/{activity_id}/hints/{hint_id}", dependencies=[Depends(require_csrf)])
def delete_hint(activity_id: int, hint_id: int, actor: User = Depends(require_permission(COURSE_MANAGE)), db: Session = Depends(get_db)) -> dict[str, bool]:
    activity = run(lambda: service.staff_activity(db, actor, activity_id))
    hint = next((h for h in activity.hints if h.id == hint_id), None)
    if hint is None:
        raise HTTPException(404, "hint not found")
    db.delete(hint)
    audit.log(db, "ACTIVITY_HINT_DELETED", actor.id, "activity", activity.public_id, {"order": hint.order})
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- staff: reviews

@staff.get("/reviews")
def list_reviews(status: str = Query("PENDING_REVIEW", pattern="^(PENDING_REVIEW|NEEDS_CHANGES|APPROVED|REJECTED)$"),
                 actor: User = Depends(require_permission(ACTIVITY_REVIEW)), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [{"id": row.id, "status": row.status, "student": row.user.display_name, "activity_id": row.activity_id, "activity": row.activity.title,
             "activity_type": row.activity.type, "points": row.activity.points, "course": service.course_of(row.activity).title,
             "submission": row.submission, "submitted_at": row.submitted_at, "attempts": row.attempts, "feedback": row.feedback, "score": row.score}
            for row in service.review_queue(db, actor, status)]


@staff.post("/reviews/{progress_id}/decision", dependencies=[Depends(require_csrf)])
def decide(progress_id: int, payload: ReviewInput, actor: User = Depends(require_permission(ACTIVITY_REVIEW)), db: Session = Depends(get_db)) -> dict[str, Any]:
    row = run(lambda: service.review(db, actor, progress_id, **payload.model_dump()))
    db.commit()
    return {"id": row.id, "status": row.status, "score": row.score, "feedback": row.feedback}


# ---------------------------------------------------------------- learner

@learn.get("/courses")
def learner_courses(actor: User = Depends(require_permission(COURSE_VIEW)), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    _learner(actor)
    return [service.course_outline(db, actor, course) for course in service.learner_courses(db, actor)]


@learn.get("/courses/{public_id}")
def learner_course(public_id: str, actor: User = Depends(require_permission(COURSE_VIEW)), db: Session = Depends(get_db)) -> dict[str, Any]:
    _learner(actor)
    return service.course_outline(db, actor, run(lambda: service.learner_course(db, actor, public_id)))


@learn.get("/lessons/{public_id}", response_model=LearnerLesson)
def learner_lesson(public_id: str, actor: User = Depends(require_permission(COURSE_VIEW)), db: Session = Depends(get_db)) -> dict[str, Any]:
    _learner(actor)
    return run(lambda: service.learner_lesson(db, actor, public_id))


@learn.get("/activities/{public_id}", response_model=LearnerActivity)
def learner_activity(public_id: str, actor: User = Depends(require_permission(COURSE_VIEW)), db: Session = Depends(get_db)) -> dict[str, Any]:
    _learner(actor)
    return service.learner_view(db, actor, run(lambda: service.learner_activity(db, actor, public_id)))


@learn.post("/activities/{public_id}/start", dependencies=[Depends(require_csrf)], response_model=LearnerActivity)
def start_activity(public_id: str, actor: User = Depends(require_permission(ACTIVITY_SUBMIT)), db: Session = Depends(get_db)) -> dict[str, Any]:
    _learner(actor)
    activity = run(lambda: service.learner_activity(db, actor, public_id))
    run(lambda: service.start(db, actor, activity))
    db.commit()
    return service.learner_view(db, actor, activity)


@learn.post("/activities/{public_id}/submit", dependencies=[Depends(require_csrf)], response_model=LearnerSubmissionResult)
def submit_activity(public_id: str, payload: SubmissionInput, actor: User = Depends(require_permission(ACTIVITY_SUBMIT)), db: Session = Depends(get_db)) -> dict[str, Any]:
    _learner(actor)
    activity = run(lambda: service.learner_activity(db, actor, public_id))
    result = run(lambda: service.submit(db, actor, activity, payload.payload()))
    db.commit()
    return result


@learn.post("/activities/{public_id}/hints/{hint_id}", dependencies=[Depends(require_csrf)], response_model=LearnerActivity)
def unlock_hint(public_id: str, hint_id: int, actor: User = Depends(require_permission(ACTIVITY_SUBMIT)), db: Session = Depends(get_db)) -> dict[str, Any]:
    _learner(actor)
    activity = run(lambda: service.learner_activity(db, actor, public_id))
    run(lambda: service.use_hint(db, actor, activity, hint_id))
    db.commit()
    return service.learner_view(db, actor, activity)
