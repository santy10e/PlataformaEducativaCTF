"""Curriculum module (SPEC phase 4): authoring scope, learner access, activity types, review and seed."""

import json
from typing import Any

import pytest
from helpers import Caller, make_role, make_user
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.ctf_service import save_event, save_taxonomy
from app.models import (
    Category,
    ChallengeProgress,
    Difficulty,
    Notification,
    Permission,
    Role,
    SchoolClass,
    User,
)
from app.modules.curriculum.models import ActivityProgress, Course, HintUsage
from app.modules.curriculum.permissions import DEFAULT_GRANTS
from app.scoring_service import now_utc

STAFF = "/api/v1/curriculum"
LEARN = "/api/v1/learn"
QUIZ = {
    "questions": [
        {"id": "q1", "prompt": "¿Qué comando lista archivos?", "kind": "single", "options": ["ls", "cd", "rm"], "correct": [0], "points": 1},
        {"id": "q2", "prompt": "Elige protocolos de transporte", "kind": "multiple", "options": ["TCP", "HTTP", "UDP"], "correct": [0, 2], "points": 2},
        {"id": "q3", "prompt": "Puerto por defecto de HTTPS", "kind": "text", "accepted": ["443"], "points": 1},
    ],
    "max_attempts": 2,
}


@pytest.fixture
def school(db: DbSession) -> dict[str, Any]:
    make_role(db, "INSTRUCTOR", tuple(DEFAULT_GRANTS["INSTRUCTOR"]))
    make_role(db, "STUDENT", tuple(DEFAULT_GRANTS["STUDENT"]))
    make_role(db, "ADMIN", tuple(DEFAULT_GRANTS["INSTRUCTOR"]))
    teacher = make_user(db, "teacher", "INSTRUCTOR")
    other = make_user(db, "other_teacher", "INSTRUCTOR")
    learner = make_user(db, "learner", "STUDENT")
    outsider = make_user(db, "outsider", "STUDENT")
    own = SchoolClass(name="1A", teacher_user_id=teacher.id, students=[learner])
    foreign = SchoolClass(name="1B", teacher_user_id=other.id, students=[outsider])
    db.add_all([own, foreign])
    db.commit()
    return {"teacher": teacher, "other": other, "learner": learner, "outsider": outsider, "own": own, "foreign": foreign}


def build_course(call: Caller, teacher: User, class_id: int, *, activities: list[dict[str, Any]]) -> dict[str, Any]:
    course = call(teacher, "POST", f"{STAFF}/courses", json={"title": "Fundamentos", "status": "PUBLISHED"}).json()
    module = call(teacher, "POST", f"{STAFF}/courses/{course['id']}/modules", json={"title": "Mes 1", "status": "PUBLISHED"}).json()
    lesson = call(teacher, "POST", f"{STAFF}/modules/{module['id']}/lessons", json={"title": "Terminal", "content_markdown": "Contenido **propio**", "status": "PUBLISHED"}).json()
    created = []
    for spec in activities:
        response = call(teacher, "POST", f"{STAFF}/lessons/{lesson['id']}/activities", json={"status": "PUBLISHED", **spec})
        assert response.status_code == 200, response.text
        created.append(response.json())
    assert call(teacher, "PUT", f"{STAFF}/courses/{course['id']}/classes", json={"class_ids": [class_id]}).status_code == 200
    return {"course": course, "module": module, "lesson": lesson, "activities": created}


def test_teachers_only_author_their_own_courses(db: DbSession, call: Caller, school: dict[str, Any]) -> None:
    built = build_course(call, school["teacher"], school["own"].id, activities=[{"type": "lesson_read", "title": "Leer"}])
    course_id = built["course"]["id"]
    other = school["other"]
    assert call(other, "GET", f"{STAFF}/courses/{course_id}").status_code == 404
    assert call(other, "PUT", f"{STAFF}/courses/{course_id}", json={"title": "robado"}).status_code == 404
    assert call(other, "POST", f"{STAFF}/courses/{course_id}/modules", json={"title": "intruso"}).status_code == 404
    assert call(other, "PUT", f"{STAFF}/activities/{built['activities'][0]['id']}", json={"type": "lesson_read", "title": "x2"}).status_code == 404
    assert [c["id"] for c in call(other, "GET", f"{STAFF}/courses").json()] == []
    # Assigning someone else's class is refused.
    assert call(school["teacher"], "PUT", f"{STAFF}/courses/{course_id}/classes", json={"class_ids": [school["foreign"].id]}).status_code == 403


def test_learners_see_only_published_content_of_their_classes(db: DbSession, call: Caller, school: dict[str, Any]) -> None:
    built = build_course(call, school["teacher"], school["own"].id, activities=[{"type": "lesson_read", "title": "Leer"}, {"type": "lesson_read", "title": "Borrador", "status": "DRAFT"}])
    learner, outsider = school["learner"], school["outsider"]
    courses = call(learner, "GET", f"{LEARN}/courses").json()
    assert [c["title"] for c in courses] == ["Fundamentos"]
    titles = [a["title"] for lesson in courses[0]["modules"][0]["lessons"] for a in lesson["activities"]]
    assert titles == ["Leer"]
    lesson_id = built["lesson"]["public_id"]
    assert call(learner, "GET", f"{LEARN}/lessons/{lesson_id}").status_code == 200
    assert call(outsider, "GET", f"{LEARN}/courses").json() == []
    assert call(outsider, "GET", f"{LEARN}/lessons/{lesson_id}").status_code == 404
    assert call(outsider, "GET", f"{LEARN}/activities/{built['activities'][0]['public_id']}").status_code == 404
    # Drafts stay invisible even with a direct link.
    assert call(learner, "GET", f"{LEARN}/activities/{built['activities'][1]['public_id']}").status_code == 404
    call(school["teacher"], "PUT", f"{STAFF}/lessons/{built['lesson']['id']}", json={"title": "Terminal", "status": "DRAFT"})
    assert call(learner, "GET", f"{LEARN}/lessons/{lesson_id}").status_code == 404
    # Learners never reach authoring endpoints.
    assert call(learner, "GET", f"{STAFF}/courses").status_code == 403


def test_learner_payloads_never_contain_answers(db: DbSession, call: Caller, school: dict[str, Any]) -> None:
    built = build_course(call, school["teacher"], school["own"].id, activities=[
        {"type": "quiz", "title": "Cuestionario", "config": QUIZ},
        {"type": "exercise", "title": "Ejercicio", "config": {"accepted_answers": ["root-secreto"]}},
    ])
    call(school["teacher"], "POST", f"{STAFF}/activities/{built['activities'][0]['id']}/hints", json={"order": 1, "cost": 5, "content_markdown": "pista-oculta"})
    lesson = call(school["learner"], "GET", f"{LEARN}/lessons/{built['lesson']['public_id']}")
    body = json.dumps(lesson.json())
    for secret in ('"correct"', '"accepted"', "root-secreto", "accepted_answers", "pista-oculta", '"challenge_id"'):
        assert secret not in body
    quiz = lesson.json()["activities"][0]
    assert quiz["config"]["questions"][0] == {"id": "q1", "prompt": "¿Qué comando lista archivos?", "kind": "single", "options": ["ls", "cd", "rm"], "points": 1}
    assert quiz["hints"] == [{"id": quiz["hints"][0]["id"], "order": 1, "cost": 5, "unlocked": False, "content_markdown": None}]


def test_quiz_is_autocorrected_keeps_best_score_and_limits_attempts(db: DbSession, call: Caller, school: dict[str, Any]) -> None:
    built = build_course(call, school["teacher"], school["own"].id, activities=[{"type": "quiz", "title": "Cuestionario", "points": 100, "config": QUIZ}])
    path = f"{LEARN}/activities/{built['activities'][0]['public_id']}/submit"
    learner = school["learner"]
    first = call(learner, "POST", path, json={"answers": {"q1": 0, "q2": [0], "q3": " 443 "}})
    assert first.status_code == 200
    assert first.json()["score"] == 50  # q1 (1) + q3 (1) of 4 points
    assert first.json()["details"]["results"] == {"q1": True, "q2": False, "q3": True}
    second = call(learner, "POST", path, json={"answers": {"q1": 1, "q2": [2, 0], "q3": "80"}})
    assert second.json()["score"] == 50  # 2/4 again: best result kept
    assert call(learner, "POST", path, json={"answers": {"q1": 0, "q2": [0, 2], "q3": "443"}}).status_code == 403


def test_exercises_grade_automatically_or_go_to_review(db: DbSession, call: Caller, school: dict[str, Any]) -> None:
    built = build_course(call, school["teacher"], school["own"].id, activities=[
        {"type": "exercise", "title": "Auto", "points": 20, "config": {"accepted_answers": ["chmod 600"]}},
        {"type": "exercise", "title": "Manual", "points": 20, "config": {}},
    ])
    learner = school["learner"]
    auto = f"{LEARN}/activities/{built['activities'][0]['public_id']}/submit"
    wrong = call(learner, "POST", auto, json={"answer": "chmod 777"}).json()
    assert wrong["status"] == "IN_PROGRESS" and "no coincide" in wrong["feedback"]
    right = call(learner, "POST", auto, json={"answer": "  CHMOD   600 "}).json()
    assert right["status"] == "APPROVED" and right["score"] == 20
    manual = f"{LEARN}/activities/{built['activities'][1]['public_id']}/submit"
    assert call(learner, "POST", manual, json={"answer": "Mi explicación"}).json()["status"] == "PENDING_REVIEW"
    assert call(learner, "POST", manual, json={"answer": "otra"}).status_code == 422


def test_project_review_flow_is_scoped_audited_and_notifies(db: DbSession, call: Caller, school: dict[str, Any]) -> None:
    built = build_course(call, school["teacher"], school["own"].id, activities=[{"type": "project", "title": "Informe", "points": 40, "config": {"accept": ["text", "url"]}}])
    learner, teacher = school["learner"], school["teacher"]
    submit = f"{LEARN}/activities/{built['activities'][0]['public_id']}/submit"
    assert call(learner, "POST", submit, json={"url": "javascript:alert(1)"}).status_code == 422
    assert call(learner, "POST", submit, json={"text": "Informe v1", "url": "https://example.edu/informe"}).json()["status"] == "PENDING_REVIEW"

    queue = call(teacher, "GET", f"{STAFF}/reviews").json()
    assert [row["activity"] for row in queue] == ["Informe"]
    progress_id = queue[0]["id"]
    assert call(school["other"], "GET", f"{STAFF}/reviews").json() == []
    assert call(school["other"], "POST", f"{STAFF}/reviews/{progress_id}/decision", json={"decision": "APPROVED", "score": 40}).status_code == 404
    assert call(teacher, "POST", f"{STAFF}/reviews/{progress_id}/decision", json={"decision": "NEEDS_CHANGES"}).status_code == 422
    assert call(teacher, "POST", f"{STAFF}/reviews/{progress_id}/decision", json={"decision": "NEEDS_CHANGES", "feedback": "Añade conclusiones"}).status_code == 200

    assert call(learner, "POST", submit, json={"text": "Informe v2 con conclusiones"}).json()["status"] == "PENDING_REVIEW"
    assert call(teacher, "POST", f"{STAFF}/reviews/{progress_id}/decision", json={"decision": "APPROVED", "score": 41}).status_code == 422
    approved = call(teacher, "POST", f"{STAFF}/reviews/{progress_id}/decision", json={"decision": "APPROVED", "score": 36, "feedback": "Bien"})
    assert approved.json() == {"id": progress_id, "status": "APPROVED", "score": 36, "feedback": "Bien"}
    notices = db.scalars(select(Notification).where(Notification.user_id == learner.id, Notification.event_type == "ACTIVITY_REVIEWED")).all()
    assert [n.payload["decision"] for n in notices] == ["NEEDS_CHANGES", "APPROVED"]
    assert call(learner, "POST", submit, json={"text": "otra vez"}).status_code == 422


def test_prerequisites_lock_activities_and_reject_cycles(db: DbSession, call: Caller, school: dict[str, Any]) -> None:
    built = build_course(call, school["teacher"], school["own"].id, activities=[{"type": "lesson_read", "title": "Primero"}])
    first = built["activities"][0]
    lesson_id = built["lesson"]["id"]
    teacher, learner = school["teacher"], school["learner"]
    second = call(teacher, "POST", f"{STAFF}/lessons/{lesson_id}/activities", json={"type": "exercise", "title": "Segundo", "status": "PUBLISHED", "description_markdown": "enunciado-protegido", "config": {"accepted_answers": ["x"]}, "prerequisite_ids": [first["id"]]}).json()
    locked = call(learner, "GET", f"{LEARN}/activities/{second['public_id']}").json()
    assert locked["locked"] is True and locked["lock_reason"] == "Completa primero: Primero" and locked["description_markdown"] == ""
    assert call(learner, "POST", f"{LEARN}/activities/{second['public_id']}/submit", json={"answer": "x"}).status_code == 403
    call(learner, "POST", f"{LEARN}/activities/{first['public_id']}/submit", json={})
    assert call(learner, "GET", f"{LEARN}/activities/{second['public_id']}").json()["locked"] is False
    # first -> second -> first would be a cycle.
    cycle = call(teacher, "PUT", f"{STAFF}/activities/{first['id']}", json={"type": "lesson_read", "title": "Primero", "status": "PUBLISHED", "prerequisite_ids": [second["id"]]})
    assert cycle.status_code == 422 and "cycles" in cycle.text
    other_course = build_course(call, teacher, school["own"].id, activities=[{"type": "lesson_read", "title": "Ajena"}])
    cross = call(teacher, "PUT", f"{STAFF}/activities/{second['id']}", json={"type": "exercise", "title": "Segundo", "config": {}, "prerequisite_ids": [other_course["activities"][0]["id"]]})
    assert cross.status_code == 422


def test_hints_unlock_in_order_and_record_their_cost(db: DbSession, call: Caller, school: dict[str, Any]) -> None:
    built = build_course(call, school["teacher"], school["own"].id, activities=[{"type": "exercise", "title": "Con pistas", "config": {"accepted_answers": ["ok"]}}])
    activity = built["activities"][0]
    for order, cost in ((1, 5), (2, 10)):
        call(school["teacher"], "POST", f"{STAFF}/activities/{activity['id']}/hints", json={"order": order, "cost": cost, "content_markdown": f"pista {order}"})
    hints = call(school["learner"], "GET", f"{LEARN}/activities/{activity['public_id']}").json()["hints"]
    base = f"{LEARN}/activities/{activity['public_id']}/hints"
    assert call(school["learner"], "POST", f"{base}/{hints[1]['id']}").status_code == 422
    unlocked = call(school["learner"], "POST", f"{base}/{hints[0]['id']}").json()["hints"]
    assert unlocked[0]["content_markdown"] == "pista 1" and unlocked[1]["content_markdown"] is None
    assert [u.cost for u in db.scalars(select(HintUsage)).all()] == [5]


def test_ctf_activities_reference_owned_challenges_and_follow_their_progress(db: DbSession, call: Caller, school: dict[str, Any]) -> None:
    from app.ctf_service import save_challenge

    teacher, other, learner = school["teacher"], school["other"], school["learner"]
    category = save_taxonomy(db, Category, None, name="Web", color="#123456", sort_order=0, multiplier=1.0)
    difficulty = save_taxonomy(db, Difficulty, None, name="Inicial", color="#654321", sort_order=0, multiplier=1.0)
    event = save_event(db, teacher, None, name="CTF", status="PUBLISHED", visibility="ASSIGNED", mode="JEOPARDY", rules_markdown="", starts_at=None, ends_at=None, class_ids=[school["own"].id])
    foreign_event = save_event(db, other, None, name="Ajeno", status="PUBLISHED", visibility="ASSIGNED", mode="JEOPARDY", rules_markdown="", starts_at=None, ends_at=None, class_ids=[school["foreign"].id])
    common = {"category_id": category.id, "difficulty_id": difficulty.id, "description_markdown": "", "status": "PUBLISHED", "points": 100, "sort_order": 0,
              "delivery_type": "STATIC", "delivery_config": {}, "module_id": None, "flag_hash": None, "prerequisite_ids": []}
    mine = save_challenge(db, event, None, slug="mine", title="Mío", **common)
    theirs = save_challenge(db, foreign_event, None, slug="theirs", title="Ajeno", **common)
    db.commit()

    built = build_course(call, teacher, school["own"].id, activities=[])
    lesson_id = built["lesson"]["id"]
    rejected = call(teacher, "POST", f"{STAFF}/lessons/{lesson_id}/activities", json={"type": "ctf_challenge", "title": "Robado", "config": {"challenge_id": theirs.id}})
    assert rejected.status_code == 422
    activity = call(teacher, "POST", f"{STAFF}/lessons/{lesson_id}/activities", json={"type": "ctf_challenge", "title": "Reto", "status": "PUBLISHED", "config": {"challenge_id": mine.id}}).json()

    view = call(learner, "GET", f"{LEARN}/activities/{activity['public_id']}").json()
    assert view["status"] == "NOT_STARTED" and view["config"] == {}
    assert view["ctf"] == {"available": True, "event_public_id": event.public_id, "challenge_public_id": mine.public_id, "state": "NOT_STARTED"}
    assert call(learner, "POST", f"{LEARN}/activities/{activity['public_id']}/submit", json={}).status_code == 422
    db.add(ChallengeProgress(user_id=learner.id, challenge_id=mine.id, started_at=now_utc(), completed_at=now_utc()))
    db.commit()
    assert call(learner, "GET", f"{LEARN}/activities/{activity['public_id']}").json()["status"] == "APPROVED"


def test_invalid_configuration_and_type_changes_are_rejected(db: DbSession, call: Caller, school: dict[str, Any]) -> None:
    built = build_course(call, school["teacher"], school["own"].id, activities=[{"type": "lesson_read", "title": "Leer"}])
    lesson_id, activity = built["lesson"]["id"], built["activities"][0]
    teacher = school["teacher"]
    bad_quiz = {"questions": [{"id": "q1", "prompt": "?", "kind": "single", "options": ["a", "b"], "correct": [5]}]}
    assert call(teacher, "POST", f"{STAFF}/lessons/{lesson_id}/activities", json={"type": "quiz", "title": "Mal", "config": bad_quiz}).status_code == 422
    assert call(teacher, "POST", f"{STAFF}/lessons/{lesson_id}/activities", json={"type": "lesson_read", "title": "Extra", "config": {"x": 1}}).status_code == 422
    assert call(teacher, "POST", f"{STAFF}/lessons/{lesson_id}/activities", json={"type": "lesson_read", "title": "Cat", "category_id": 99999}).status_code == 422
    assert call(teacher, "PUT", f"{STAFF}/activities/{activity['id']}", json={"type": "quiz", "title": "Leer", "config": QUIZ}).status_code == 422


def test_templates_are_admin_managed_and_duplicated_by_teachers(db: DbSession, call: Caller, school: dict[str, Any]) -> None:
    from app.modules.curriculum.seed_plan import seed_curriculum_plan

    seed_curriculum_plan(db)
    seed_curriculum_plan(db)
    db.commit()
    template = db.scalar(select(Course).where(Course.owner_user_id.is_(None)))
    assert template is not None and len(template.modules) == 9
    teacher = school["teacher"]
    listed = call(teacher, "GET", f"{STAFF}/courses").json()
    assert [(c["title"], c["can_manage"]) for c in listed] == [("Ciberseguridad — plan de 9 meses", False)]
    assert call(teacher, "PUT", f"{STAFF}/courses/{template.id}", json={"title": "cambio"}).status_code == 404
    copy = call(teacher, "POST", f"{STAFF}/courses/{template.id}/duplicate").json()
    assert copy["can_manage"] is True and copy["status"] == "DRAFT" and len(copy["modules"]) == 9
    assert copy["modules"][0]["lessons"][0]["activities"][0]["type"] == "lesson_read"


def test_course_progress_counts_completed_activities_per_module(db: DbSession, call: Caller, school: dict[str, Any]) -> None:
    built = build_course(call, school["teacher"], school["own"].id, activities=[{"type": "lesson_read", "title": "Lectura A"}, {"type": "lesson_read", "title": "Lectura B"}])
    call(school["learner"], "POST", f"{LEARN}/activities/{built['activities'][0]['public_id']}/submit", json={})
    progress = call(school["teacher"], "GET", f"{STAFF}/courses/{built['course']['id']}/progress").json()
    assert progress["students"] == [{"student_id": school["learner"].id, "display_name": "learner", "modules": [{"module_public_id": built["module"]["public_id"], "completed": 1, "total": 2}], "pending_review": False}]
    assert db.scalar(select(ActivityProgress.status)) == "APPROVED"


def test_seed_grants_new_permissions_once_and_keeps_admin_choices(db: DbSession, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.seed as seed_module

    monkeypatch.setattr(seed_module.settings, "admin_password", "Seed-Admin-Pass-2026")
    monkeypatch.setattr(seed_module, "engine", db.get_bind())
    seed_module.seed()
    instructor = db.scalar(select(Role).where(Role.name == "INSTRUCTOR"))
    assert instructor is not None
    codes = {p.code for p in instructor.permissions}
    assert {"course.manage", "activity.review"} <= codes and "activity.submit" not in codes
    # An administrator removes a permission; a later seed must respect that decision.
    instructor.permissions = [p for p in instructor.permissions if p.code != "activity.review"]
    db.commit()
    seed_module.seed()
    db.expire_all()
    assert "activity.review" not in {p.code for p in db.scalar(select(Role).where(Role.name == "INSTRUCTOR")).permissions}  # type: ignore[union-attr]
    assert db.scalar(select(Permission.id).where(Permission.code == "course.view")) is not None
    assert len(db.scalars(select(Course).where(Course.owner_user_id.is_(None))).all()) == 1
