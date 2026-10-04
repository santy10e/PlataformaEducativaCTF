import re
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app import audit
from app.dependencies import get_db, require_csrf, require_permission
from app.imports_service import confirm_import, preview_csv
from app.models import ImportJob, Session, User
from app.security import hash_password
from app.users_service import (
    create_user,
    deactivate_user,
    get_visible_user,
    list_users,
    serialize_user,
    update_user,
)

router = APIRouter(prefix="/api/v1", tags=["users and imports"])
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class UserCreateInput(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    password: str = Field(min_length=12, max_length=256)
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    role: Literal["STUDENT", "INSTRUCTOR", "ADMIN"] = "STUDENT"
    email: str | None = Field(default=None, max_length=254)
    class_ids: list[int] = Field(default_factory=list, max_length=50)

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name is required")
        return value

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip().lower()
        if not EMAIL_RE.fullmatch(normalized):
            raise ValueError("invalid email address")
        return normalized


class UserUpdateInput(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: str | None = Field(default=None, max_length=254)


class ActiveInput(BaseModel):
    is_active: bool


class PasswordResetInput(BaseModel):
    temporary_password: str = Field(min_length=12, max_length=256)


class CsvPreviewInput(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    csv_content: str = Field(min_length=1, max_length=2_000_000)


class UserOutput(BaseModel):
    id: int
    username: str
    display_name: str
    first_name: str
    last_name: str
    email: str | None
    roles: list[str]
    is_active: bool
    must_change_password: bool
    class_ids: list[int]


class UserPageOutput(BaseModel):
    items: list[UserOutput]
    total: int
    page: int
    page_size: int


class ImportRowOutput(BaseModel):
    row_number: int
    username: str
    first_name: str
    last_name: str
    display_name: str
    course: str
    email: str | None
    valid: bool
    errors: list[str]


class ImportPreviewOutput(BaseModel):
    job_id: str
    status: str
    row_count: int
    valid_count: int
    error_count: int
    items: list[ImportRowOutput]


class UserStatusOutput(BaseModel):
    id: int
    is_active: bool


class OkOutput(BaseModel):
    ok: bool


class ImportResultOutput(BaseModel):
    job_id: str
    status: str
    imported_count: int
    class_count: int
    already_imported: bool


@router.get("/users", response_model=UserPageOutput)
def users(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str | None = Query(None, max_length=120),
    role: str | None = Query(None, pattern=r"^(student|instructor|admin)$"),
    actor: User = Depends(require_permission("user.view")),
    db: DbSession = Depends(get_db),
) -> dict[str, object]:
    return list_users(db, actor, page, page_size, search, role)


@router.post("/users", dependencies=[Depends(require_csrf)], response_model=UserOutput)
def create(
    payload: UserCreateInput,
    actor: User = Depends(require_permission("user.create")),
    db: DbSession = Depends(get_db),
) -> dict[str, object]:
    try:
        user = create_user(
            db,
            actor,
            username=payload.username,
            password=payload.password,
            first_name=payload.first_name,
            last_name=payload.last_name,
            role_name=payload.role,
            email=payload.email,
            class_ids=payload.class_ids,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    audit.log(db, "USER_CREATED", actor.id, "user", str(user.id), {"role": payload.role})
    db.commit()
    return serialize_user(user)


@router.get("/users/{user_id}", response_model=UserOutput)
def get_user(user_id: int, actor: User = Depends(require_permission("user.view")), db: DbSession = Depends(get_db)) -> dict[str, object]:
    user = get_visible_user(db, actor, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return serialize_user(user)


@router.put("/users/{user_id}", dependencies=[Depends(require_csrf)], response_model=UserOutput)
def put_user(
    user_id: int,
    payload: UserUpdateInput,
    actor: User = Depends(require_permission("user.update")),
    db: DbSession = Depends(get_db),
) -> dict[str, object]:
    user = get_visible_user(db, actor, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    try:
        update_user(db, user, first_name=payload.first_name.strip(), last_name=payload.last_name.strip(), email=payload.email)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    audit.log(db, "USER_MODIFIED", actor.id, "user", str(user.id))
    db.commit()
    return serialize_user(user)


@router.patch("/users/{user_id}/status", dependencies=[Depends(require_csrf)], response_model=UserStatusOutput)
def set_user_status(
    user_id: int,
    payload: ActiveInput,
    actor: User = Depends(require_permission("user.update")),
    db: DbSession = Depends(get_db),
) -> dict[str, object]:
    user = get_visible_user(db, actor, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    if not payload.is_active:
        deactivate_user(db, user)
    else:
        user.is_active = True
    audit.log(db, "USER_MODIFIED", actor.id, "user", str(user.id), {"is_active": payload.is_active})
    db.commit()
    return {"id": user.id, "is_active": user.is_active}


@router.post("/users/{user_id}/password-reset", dependencies=[Depends(require_csrf)], response_model=OkOutput)
def reset_password(
    user_id: int,
    payload: PasswordResetInput,
    actor: User = Depends(require_permission("user.password_reset")),
    db: DbSession = Depends(get_db),
) -> dict[str, bool]:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    user.password_hash = hash_password(payload.temporary_password)
    user.must_change_password = True
    for session in db.scalars(select(Session).where(Session.user_id == user.id, Session.revoked_at.is_(None))).all():
        session.revoked_at = datetime.now(UTC).replace(tzinfo=None)
    audit.log(db, "USER_PASSWORD_RESET", actor.id, "user", str(user.id))
    db.commit()
    return {"ok": True}


@router.post("/users/import/preview", dependencies=[Depends(require_csrf)], response_model=ImportPreviewOutput)
def import_preview(
    payload: CsvPreviewInput,
    actor: User = Depends(require_permission("import.preview")),
    db: DbSession = Depends(get_db),
) -> dict[str, object]:
    try:
        job, rows = preview_csv(db, actor.id, payload.filename, payload.csv_content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    audit.log(db, "USER_IMPORT_PREVIEWED", actor.id, "import_job", job.public_id, {"rows": job.row_count, "valid": job.valid_count, "errors": job.error_count})
    db.commit()
    return {"job_id": job.public_id, "status": job.status, "row_count": job.row_count, "valid_count": job.valid_count, "error_count": job.error_count, "items": rows}


@router.post("/users/import/{job_id}/confirm", dependencies=[Depends(require_csrf)], response_model=ImportResultOutput)
def confirm_user_import(
    job_id: str,
    actor: User = Depends(require_permission("import.execute")),
    db: DbSession = Depends(get_db),
) -> dict[str, object]:
    job = db.scalar(select(ImportJob).where(ImportJob.public_id == job_id, ImportJob.actor_user_id == actor.id))
    if job is None:
        raise HTTPException(status_code=404, detail="import job not found")
    result = confirm_import(db, job)
    if result.get("already_imported") is not True:
        audit.log(db, "USER_IMPORT_CONFIRMED", actor.id, "import_job", job.public_id, {"imported": result["imported_count"], "classes": result["class_count"]})
    db.commit()
    return result
