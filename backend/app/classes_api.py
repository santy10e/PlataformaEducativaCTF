from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from app import audit
from app.classes_service import (
    create_class,
    delete_class,
    get_class,
    list_classes,
    replace_students,
    serialize_class,
    update_class,
)
from app.dependencies import get_db, require_csrf, require_permission
from app.models import User
from app.users_service import serialize_user

router = APIRouter(prefix="/api/v1/classes", tags=["classes"])


class ClassInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    academic_period: str = Field(default="", max_length=32)
    description: str = Field(default="", max_length=255)
    teacher_user_id: int | None = None


class ClassStudentsInput(BaseModel):
    student_ids: list[int] = Field(max_length=500)


class ClassOutput(BaseModel):
    id: int
    name: str
    academic_period: str
    description: str
    teacher_user_id: int | None
    teacher_name: str | None
    student_count: int


class ClassPageOutput(BaseModel):
    items: list[ClassOutput]
    total: int
    page: int
    page_size: int


class ClassMembersOutput(BaseModel):
    class_id: int
    student_count: int
    student_ids: list[int]


class OkOutput(BaseModel):
    ok: bool


@router.get("", response_model=ClassPageOutput)
def classes(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str | None = Query(None, max_length=120),
    actor: User = Depends(require_permission("class.view")),
    db: DbSession = Depends(get_db),
) -> dict[str, object]:
    return list_classes(db, actor, page, page_size, search)


@router.post("", dependencies=[Depends(require_csrf)], response_model=ClassOutput)
def post_class(payload: ClassInput, actor: User = Depends(require_permission("class.create")), db: DbSession = Depends(get_db)) -> dict[str, object]:
    try:
        item = create_class(db, actor, name=payload.name, academic_period=payload.academic_period, description=payload.description, teacher_user_id=payload.teacher_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    audit.log(db, "CLASS_CREATED", actor.id, "class", str(item.id))
    db.commit()
    return serialize_class(db, item)


@router.get("/{class_id}", response_model=ClassOutput)
def get_one(class_id: int, actor: User = Depends(require_permission("class.view")), db: DbSession = Depends(get_db)) -> dict[str, object]:
    item = get_class(db, actor, class_id)
    if item is None:
        raise HTTPException(status_code=404, detail="class not found")
    return serialize_class(db, item)


@router.put("/{class_id}", dependencies=[Depends(require_csrf)], response_model=ClassOutput)
def put_class(class_id: int, payload: ClassInput, actor: User = Depends(require_permission("class.update")), db: DbSession = Depends(get_db)) -> dict[str, object]:
    item = get_class(db, actor, class_id)
    if item is None:
        raise HTTPException(status_code=404, detail="class not found")
    try:
        update_class(db, item, name=payload.name, academic_period=payload.academic_period, description=payload.description, teacher_user_id=payload.teacher_user_id, actor=actor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    audit.log(db, "CLASS_MODIFIED", actor.id, "class", str(item.id))
    db.commit()
    return serialize_class(db, item)


@router.delete("/{class_id}", dependencies=[Depends(require_csrf)], response_model=OkOutput)
def remove_class(class_id: int, actor: User = Depends(require_permission("class.delete")), db: DbSession = Depends(get_db)) -> dict[str, bool]:
    item = get_class(db, actor, class_id)
    if item is None:
        raise HTTPException(status_code=404, detail="class not found")
    try:
        delete_class(db, item)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    audit.log(db, "CLASS_DELETED", actor.id, "class", str(class_id))
    db.commit()
    return {"ok": True}


@router.get("/{class_id}/students")
def get_students(class_id: int, actor: User = Depends(require_permission("class.view")), db: DbSession = Depends(get_db)) -> list[dict[str, object]]:
    item = get_class(db, actor, class_id)
    if item is None:
        raise HTTPException(status_code=404, detail="class not found")
    return [serialize_user(student) for student in item.students]


@router.put("/{class_id}/students", dependencies=[Depends(require_csrf)], response_model=ClassMembersOutput)
def put_students(class_id: int, payload: ClassStudentsInput, actor: User = Depends(require_permission("class.manage_students")), db: DbSession = Depends(get_db)) -> dict[str, object]:
    item = get_class(db, actor, class_id)
    if item is None:
        raise HTTPException(status_code=404, detail="class not found")
    try:
        students = replace_students(db, item, payload.student_ids)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    audit.log(db, "CLASS_STUDENTS_MODIFIED", actor.id, "class", str(item.id), {"student_count": len(students)})
    db.commit()
    return {"class_id": item.id, "student_count": len(students), "student_ids": [student.id for student in students]}
