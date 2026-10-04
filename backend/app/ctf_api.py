import hashlib
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Literal, cast
from urllib.parse import unquote
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app import audit
from app.challenge_import_service import (
    MAX_ARCHIVE_BYTES,
    ImportValidationError,
    export_challenge,
    export_event,
    import_package,
    parse_package,
    preview_json,
)
from app.ctf_service import (
    categories,
    create_hint,
    delete_event,
    delete_taxonomy,
    difficulties,
    duplicate_challenge,
    duplicate_event,
    get_event,
    list_challenges,
    list_events,
    save_challenge,
    save_event,
    save_taxonomy,
    soft_delete_challenge,
    student_challenges,
    student_events,
    update_hint,
)
from app.dependencies import current_session, get_db, require_csrf, require_permission
from app.models import Category, Challenge, ChallengeFile, CtfEvent, Difficulty, Hint, User
from app.settings_service import get as get_setting
from app.users_service import user_roles

router = APIRouter(prefix="/api/v1/ctf", tags=["ctf"])
MAX_FILE_SIZE = 10 * 1024 * 1024


class TaxonomyInput(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    color: str = "#587666"
    sort_order: int = Field(default=0, ge=0, le=10000)
    multiplier: float = Field(default=1, gt=0, le=10)

    @field_validator("color")
    @classmethod
    def valid_color(cls, value: str) -> str:
        import re
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
            raise ValueError("color must be a six-digit hex color")
        return value


class EventInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    status: Literal["DRAFT", "PUBLISHED", "ARCHIVED"] = "DRAFT"
    visibility: Literal["ASSIGNED", "PUBLIC"] = "ASSIGNED"
    mode: Literal["JEOPARDY"] = "JEOPARDY"
    rules_markdown: str = Field(default="", max_length=30000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    class_ids: list[int] = Field(default_factory=list, max_length=200)
    scoring_strategy: Literal["FIXED", "TIME_DECAY", "DYNAMIC_BY_SOLVES"] = "FIXED"
    scoring_config: dict[str, object] = Field(default_factory=dict)
    max_attempts: int | None = Field(default=None, ge=1, le=1000)


class ChallengeInput(BaseModel):
    category_id: int
    difficulty_id: int
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: str = Field(min_length=2, max_length=180)
    description_markdown: str = Field(default="", max_length=50000)
    status: Literal["DRAFT", "PUBLISHED", "ARCHIVED"] = "DRAFT"
    points: int = Field(default=100, ge=1, le=100000)
    sort_order: int = Field(default=0, ge=0, le=10000)
    delivery_type: Literal["STATIC"] = "STATIC"
    delivery_config: dict[str, object] = Field(default_factory=dict)
    module_id: str | None = Field(default=None, max_length=100)
    prerequisite_ids: list[int] = Field(default_factory=list, max_length=100)
    scoring_strategy: Literal["FIXED", "TIME_DECAY", "DYNAMIC_BY_SOLVES"] | None = None
    scoring_config: dict[str, object] = Field(default_factory=dict)
    max_attempts: int | None = Field(default=None, ge=1, le=1000)


class HintInput(BaseModel):
    order: int = Field(ge=0, le=100)
    cost: int = Field(default=0, ge=0, le=100000)
    content_markdown: str = Field(min_length=1, max_length=10000)


def _event(item: CtfEvent) -> dict[str, object]:
    return {"id": item.id, "public_id": item.public_id, "name": item.name, "status": item.status, "visibility": item.visibility, "mode": item.mode, "rules_markdown": item.rules_markdown, "starts_at": item.starts_at, "ends_at": item.ends_at, "class_ids": [c.id for c in item.classes], "class_names": [c.name for c in item.classes], "scoring_strategy": item.scoring_strategy, "scoring_config": item.scoring_config, "max_attempts": item.max_attempts, "scoreboard_frozen": item.scoreboard_frozen}


def _challenge(item: Challenge) -> dict[str, object]:
    return {"id": item.id, "public_id": item.public_id, "event_id": item.event_id, "category_id": item.category_id, "category_name": item.category.name, "difficulty_id": item.difficulty_id, "difficulty_name": item.difficulty.name, "slug": item.slug, "title": item.title, "description_markdown": item.description_markdown, "status": item.status, "points": item.points, "sort_order": item.sort_order, "delivery_type": item.delivery_type, "delivery_config": item.delivery_config, "module_id": item.module_id, "prerequisite_ids": [p.id for p in item.prerequisites], "files": [_file_json(f) for f in item.files], "hints": [{"id": h.id, "order": h.order, "cost": h.cost, "content_markdown": h.content_markdown} for h in item.hints], "scoring_strategy": item.scoring_strategy, "scoring_config": item.scoring_config, "max_attempts": item.max_attempts}


def _get_event(db: DbSession, actor: User, event_id: int) -> CtfEvent:
    event = get_event(db, actor, event_id)
    if event is None:
        raise HTTPException(404, "event not found")
    return event


@router.get("/categories")
def get_categories(actor: User = Depends(require_permission("challenge.view")), db: DbSession = Depends(get_db)) -> list[dict[str, object]]:
    return [{"id": x.id, "name": x.name, "color": x.color, "sort_order": x.sort_order, "multiplier": x.multiplier} for x in categories(db)]


@router.get("/difficulties")
def get_difficulties(actor: User = Depends(require_permission("challenge.view")), db: DbSession = Depends(get_db)) -> list[dict[str, object]]:
    return [{"id": x.id, "name": x.name, "color": x.color, "sort_order": x.sort_order, "multiplier": x.multiplier} for x in difficulties(db)]


def _taxonomy_routes(model: type[Category] | type[Difficulty], path: str, perm: str) -> APIRouter:
    child = APIRouter(prefix=f"/{path}")

    @child.post("", dependencies=[Depends(require_csrf)])
    def create(payload: TaxonomyInput, actor: User = Depends(require_permission(f"{perm}.create")), db: DbSession = Depends(get_db)) -> dict[str, object]:
        try:
            item = save_taxonomy(db, model, None, **payload.model_dump())
        except Exception as exc:
            db.rollback()
            raise HTTPException(409, "name already exists") from exc
        audit.log(db, f"{perm.upper()}_CREATED", actor.id, perm, str(item.id))
        db.commit()
        return {"id": item.id, "name": item.name, "color": item.color, "sort_order": item.sort_order, "multiplier": item.multiplier}

    @child.put("/{item_id}", dependencies=[Depends(require_csrf)])
    def update(item_id: int, payload: TaxonomyInput, actor: User = Depends(require_permission(f"{perm}.update")), db: DbSession = Depends(get_db)) -> dict[str, object]:
        try:
            item = save_taxonomy(db, model, item_id, **payload.model_dump())
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except Exception as exc:
            db.rollback()
            raise HTTPException(409, "name already exists") from exc
        audit.log(db, f"{perm.upper()}_MODIFIED", actor.id, perm, str(item.id))
        db.commit()
        return {"id": item.id, "name": item.name, "color": item.color, "sort_order": item.sort_order, "multiplier": item.multiplier}

    @child.delete("/{item_id}", dependencies=[Depends(require_csrf)])
    def remove(item_id: int, actor: User = Depends(require_permission(f"{perm}.delete")), db: DbSession = Depends(get_db)) -> dict[str, bool]:
        try:
            delete_taxonomy(db, model, item_id)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            db.rollback()
            raise HTTPException(409, str(exc)) from exc
        audit.log(db, f"{perm.upper()}_DELETED", actor.id, perm, str(item_id))
        db.commit()
        return {"ok": True}
    return child


router.include_router(_taxonomy_routes(Category, "categories", "category"))
router.include_router(_taxonomy_routes(Difficulty, "difficulties", "difficulty"))


@router.get("/events")
def get_events(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), search: str | None = Query(None, max_length=120), actor: User = Depends(require_permission("event.manage")), db: DbSession = Depends(get_db)) -> dict[str, object]:
    result = list_events(db, actor, page, page_size, search)
    items = result["items"]
    return {**result, "items": [_event(item) for item in items if isinstance(item, CtfEvent)]} if isinstance(items, list) else result


@router.get("/events/{event_id}")
def get_event_detail(event_id: int, actor: User = Depends(require_permission("event.manage")), db: DbSession = Depends(get_db)) -> dict[str, object]:
    return _event(_get_event(db, actor, event_id))


@router.post("/events", dependencies=[Depends(require_csrf)])
def post_event(payload: EventInput, actor: User = Depends(require_permission("event.manage")), db: DbSession = Depends(get_db)) -> dict[str, object]:
    try:
        item = save_event(db, actor, None, **payload.model_dump())
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    audit.log(db, "CTF_EVENT_CREATED", actor.id, "ctf_event", item.public_id)
    db.commit()
    return _event(item)


@router.put("/events/{event_id}", dependencies=[Depends(require_csrf)])
def put_event(event_id: int, payload: EventInput, actor: User = Depends(require_permission("event.manage")), db: DbSession = Depends(get_db)) -> dict[str, object]:
    try:
        item = save_event(db, actor, event_id, **payload.model_dump())
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    audit.log(db, "CTF_EVENT_MODIFIED", actor.id, "ctf_event", item.public_id)
    db.commit()
    return _event(item)


@router.delete("/events/{event_id}", dependencies=[Depends(require_csrf)])
def remove_event(event_id: int, actor: User = Depends(require_permission("event.manage")), db: DbSession = Depends(get_db)) -> dict[str, bool]:
    item = _get_event(db, actor, event_id)
    delete_event(item)
    audit.log(db, "CTF_EVENT_ARCHIVED", actor.id, "ctf_event", item.public_id)
    db.commit()
    return {"ok": True}


@router.post("/events/{event_id}/duplicate", dependencies=[Depends(require_csrf)])
def clone_event(event_id: int, actor: User = Depends(require_permission("event.manage")), db: DbSession = Depends(get_db)) -> dict[str, object]:
    source = _get_event(db, actor, event_id)
    item = duplicate_event(db, actor, source)
    audit.log(db, "CTF_EVENT_DUPLICATED", actor.id, "ctf_event", item.public_id, {"source": source.public_id})
    db.commit()
    return _event(item)


@router.get("/events/{event_id}/challenges")
def get_event_challenges(event_id: int, actor: User = Depends(require_permission("event.manage")), db: DbSession = Depends(get_db)) -> list[dict[str, object]]:
    return [_challenge(item) for item in list_challenges(db, _get_event(db, actor, event_id), include_archived=True)]


async def _bounded_zip_body(request: Request) -> bytes:
    declared_size = request.headers.get("content-length")
    if declared_size and declared_size.isdigit() and int(declared_size) > MAX_ARCHIVE_BYTES:
        raise HTTPException(413, "ZIP exceeds the 20 MB limit")
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_ARCHIVE_BYTES:
            raise HTTPException(413, "ZIP exceeds the 20 MB limit")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/events/{event_id}/import/preview")
async def preview_challenge_import(event_id: int, request: Request,
    actor: User = Depends(require_permission("challenge.create")), db: DbSession = Depends(get_db)) -> dict[str, object]:
    event = _get_event(db, actor, event_id)
    try:
        return preview_json(parse_package(db, event, await _bounded_zip_body(request)))
    except ImportValidationError as exc:
        return {"valid": False, "errors": exc.errors, "warnings": exc.warnings, "challenges": []}


@router.post("/events/{event_id}/import/confirm", dependencies=[Depends(require_csrf)])
async def confirm_challenge_import(event_id: int, request: Request,
    actor: User = Depends(require_permission("challenge.create")), db: DbSession = Depends(get_db)) -> dict[str, object]:
    event = _get_event(db, actor, event_id)
    try:
        package = parse_package(db, event, await _bounded_zip_body(request))
        result = import_package(db, event, package, os.environ.get("CHALLENGE_FILE_STORAGE", "/app/storage/challenge-files"))
    except ImportValidationError as exc:
        db.rollback()
        raise HTTPException(422, "challenge package validation failed") from exc
    except (ValueError, OSError) as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    audit.log(db, "CHALLENGE_PACKAGE_IMPORTED", actor.id, "ctf_event", event.public_id,
        {"created": result["created"], "updated": result["updated"]})
    obsolete_storage_names = cast(list[str], result.pop("_obsolete_storage_names", []))
    new_storage_names = cast(list[str], result.pop("_new_storage_names", []))
    storage_root = Path(os.environ.get("CHALLENGE_FILE_STORAGE", "/app/storage/challenge-files")).resolve()
    try:
        db.commit()
    except Exception:
        db.rollback()
        for storage_name in new_storage_names:
            new_path = (storage_root / storage_name).resolve()
            if new_path.parent == storage_root and new_path.is_file():
                try:
                    new_path.unlink()
                except OSError:
                    pass
        raise
    for storage_name in obsolete_storage_names:
        old_path = (storage_root / storage_name).resolve()
        if old_path.parent == storage_root and old_path.is_file():
            try:
                old_path.unlink()
            except OSError:
                pass
    return result


@router.get("/events/{event_id}/export")
def export_event_package(event_id: int, actor: User = Depends(require_permission("event.manage")),
                         db: DbSession = Depends(get_db)) -> Response:
    event = _get_event(db, actor, event_id)
    content = export_event(db, event, list_challenges(db, event, include_archived=True))
    return Response(content, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{event.public_id}.zip"'})


@router.get("/events/{event_id}/challenges/{challenge_id}/export")
def export_challenge_package(event_id: int, challenge_id: int, actor: User = Depends(require_permission("event.manage")),
                             db: DbSession = Depends(get_db)) -> Response:
    event = _get_event(db, actor, event_id)
    challenge = next((item for item in list_challenges(db, event, include_archived=True) if item.id == challenge_id), None)
    if challenge is None:
        raise HTTPException(404, "challenge not found")
    content = export_challenge(db, challenge)
    return Response(content, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{challenge.slug}.zip"'})


@router.get("/events/{event_id}/challenges/{challenge_id}")
def get_challenge_detail(event_id: int, challenge_id: int, actor: User = Depends(require_permission("event.manage")), db: DbSession = Depends(get_db)) -> dict[str, object]:
    event = _get_event(db, actor, event_id)
    item = next((x for x in list_challenges(db, event, include_archived=True) if x.id == challenge_id), None)
    if item is None:
        raise HTTPException(404, "challenge not found")
    return _challenge(item)


@router.post("/events/{event_id}/challenges", dependencies=[Depends(require_csrf)])
def post_challenge(event_id: int, payload: ChallengeInput, actor: User = Depends(require_permission("challenge.create")), db: DbSession = Depends(get_db)) -> dict[str, object]:
    event = _get_event(db, actor, event_id)
    try:
        item = save_challenge(db, event, None, **payload.model_dump())
    except ValueError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    audit.log(db, "CHALLENGE_CREATED", actor.id, "challenge", item.public_id, {"event": event.public_id})
    db.commit()
    return _challenge(item)


@router.put("/events/{event_id}/challenges/{challenge_id}", dependencies=[Depends(require_csrf)])
def put_challenge(event_id: int, challenge_id: int, payload: ChallengeInput, actor: User = Depends(require_permission("challenge.update")), db: DbSession = Depends(get_db)) -> dict[str, object]:
    event = _get_event(db, actor, event_id)
    try:
        item = save_challenge(db, event, challenge_id, **payload.model_dump())
    except LookupError as exc:
        db.rollback()
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    audit.log(db, "CHALLENGE_MODIFIED", actor.id, "challenge", item.public_id)
    db.commit()
    return _challenge(item)


@router.post("/events/{event_id}/challenges/{challenge_id}/duplicate", dependencies=[Depends(require_csrf)])
def clone_challenge(event_id: int, challenge_id: int, actor: User = Depends(require_permission("challenge.create")), db: DbSession = Depends(get_db)) -> dict[str, object]:
    event = _get_event(db, actor, event_id)
    source = next((x for x in list_challenges(db, event, include_archived=False) if x.id == challenge_id), None)
    if source is None:
        raise HTTPException(404, "challenge not found")
    item = duplicate_challenge(db, event, source)
    audit.log(db, "CHALLENGE_DUPLICATED", actor.id, "challenge", item.public_id, {"source": source.public_id})
    db.commit()
    return _challenge(item)


@router.delete("/events/{event_id}/challenges/{challenge_id}", dependencies=[Depends(require_csrf)])
def remove_challenge(event_id: int, challenge_id: int, actor: User = Depends(require_permission("challenge.delete")), db: DbSession = Depends(get_db)) -> dict[str, bool]:
    event = _get_event(db, actor, event_id)
    item = next((x for x in list_challenges(db, event, include_archived=True) if x.id == challenge_id), None)
    if item is None:
        raise HTTPException(404, "challenge not found")
    soft_delete_challenge(item)
    audit.log(db, "CHALLENGE_DELETED", actor.id, "challenge", item.public_id)
    db.commit()
    return {"ok": True}


@router.post("/events/{event_id}/challenges/{challenge_id}/hints", dependencies=[Depends(require_csrf)])
def post_hint(event_id: int, challenge_id: int, payload: HintInput, actor: User = Depends(require_permission("challenge.update")), db: DbSession = Depends(get_db)) -> dict[str, object]:
    event = _get_event(db, actor, event_id)
    challenge = next((x for x in list_challenges(db, event, include_archived=True) if x.id == challenge_id), None)
    if challenge is None:
        raise HTTPException(404, "challenge not found")
    try:
        hint = create_hint(db, challenge, **payload.model_dump())
    except ValueError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc
    audit.log(db, "CHALLENGE_HINT_CREATED", actor.id, "challenge", challenge.public_id, {"order": hint.order})
    db.commit()
    return {"id": hint.id, "order": hint.order, "cost": hint.cost, "content_markdown": hint.content_markdown}


@router.put("/events/{event_id}/challenges/{challenge_id}/hints/{hint_id}", dependencies=[Depends(require_csrf)])
def put_hint(event_id: int, challenge_id: int, hint_id: int, payload: HintInput, actor: User = Depends(require_permission("challenge.update")), db: DbSession = Depends(get_db)) -> dict[str, object]:
    event = _get_event(db, actor, event_id)
    challenge = next((x for x in list_challenges(db, event, include_archived=True) if x.id == challenge_id), None)
    hint = db.get(Hint, hint_id)
    if challenge is None or hint is None or hint.challenge_id != challenge.id:
        raise HTTPException(404, "hint not found")
    try:
        update_hint(db, hint, **payload.model_dump())
    except ValueError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc
    audit.log(db, "CHALLENGE_HINT_MODIFIED", actor.id, "challenge", challenge.public_id, {"order": hint.order})
    db.commit()
    return {"id": hint.id, "order": hint.order, "cost": hint.cost, "content_markdown": hint.content_markdown}


@router.delete("/events/{event_id}/challenges/{challenge_id}/hints/{hint_id}", dependencies=[Depends(require_csrf)])
def delete_hint(event_id: int, challenge_id: int, hint_id: int, actor: User = Depends(require_permission("challenge.update")), db: DbSession = Depends(get_db)) -> dict[str, bool]:
    event = _get_event(db, actor, event_id)
    challenge = next((x for x in list_challenges(db, event, include_archived=True) if x.id == challenge_id), None)
    hint = db.get(Hint, hint_id)
    if challenge is None or hint is None or hint.challenge_id != challenge.id:
        raise HTTPException(404, "hint not found")
    db.delete(hint)
    audit.log(db, "CHALLENGE_HINT_DELETED", actor.id, "challenge", challenge.public_id, {"order": hint.order})
    db.commit()
    return {"ok": True}


@router.get("/student/events")
def get_student_events(actor: User = Depends(require_permission("challenge.view")), db: DbSession = Depends(get_db)) -> list[dict[str, object]]:
    return [{"public_id": x.public_id, "name": x.name, "starts_at": x.starts_at, "ends_at": x.ends_at, "rules_markdown": x.rules_markdown} for x in student_events(db, actor)]


@router.get("/student/events/{event_public_id}/challenges")
def get_student_challenges(event_public_id: str, actor: User = Depends(require_permission("challenge.view")), db: DbSession = Depends(get_db)) -> list[dict[str, object]]:
    # Student responses include only published challenges and safe hint/prerequisite metadata.
    event = next((item for item in student_events(db, actor) if item.public_id == event_public_id), None)
    if event is None:
        return []
    from app.models import ChallengeProgress
    from app.scoring_service import progress_for_student
    completed = set(db.scalars(select(ChallengeProgress.challenge_id).where(ChallengeProgress.user_id == actor.id, ChallengeProgress.completed_at.is_not(None))).all())
    output = []
    for challenge in list_challenges(db, event):
        if challenge.status != "PUBLISHED":
            continue
        progress = progress_for_student(db, actor, challenge)
        blocked_by = [parent.title for parent in challenge.prerequisites if parent.id not in completed]
        is_locked = bool(blocked_by)
        attempts = cast(int, progress["attempts"])
        attempt_limit = min(limit for limit in (int(get_setting(db, "max_attempts_global")), challenge.max_attempts, event.max_attempts) if limit is not None)
        output.append({"public_id": challenge.public_id, "slug": challenge.slug, "title": challenge.title, "description_markdown": "" if is_locked else challenge.description_markdown, "points": challenge.points, "category": challenge.category.name, "difficulty": challenge.difficulty.name, "sort_order": challenge.sort_order, "files": [] if is_locked else [_file_json(f) for f in challenge.files], "hint_options": [] if is_locked else [{"id": hint.id, "order": hint.order, "cost": hint.cost} for hint in challenge.hints], "prerequisites": blocked_by, "locked": is_locked, "lock_reason": ("Resuelve primero: " + ", ".join(blocked_by)) if blocked_by else None, "progress": progress, "attempts_remaining": max(0, attempt_limit - attempts) if attempt_limit is not None else None})
    return output


def _actual_file_type(content: bytes) -> str:
    signatures = ((b"%PDF-", "application/pdf"), (b"\x89PNG\r\n\x1a\n", "image/png"), (b"\xff\xd8\xff", "image/jpeg"), (b"GIF87a", "image/gif"), (b"GIF89a", "image/gif"), (b"PK\x03\x04", "application/zip"))
    for signature, media_type in signatures:
        if content.startswith(signature):
            return media_type
    try:
        content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(415, "unsupported file content") from exc
    if b"\x00" in content:
        raise HTTPException(415, "unsupported file content")
    return "text/plain"


def _file_json(item: ChallengeFile) -> dict[str, object]:
    return {"public_id": item.public_id, "name": item.original_name, "content_type": item.content_type, "size_bytes": item.size_bytes}


@router.post("/events/{event_id}/challenges/{challenge_id}/files", dependencies=[Depends(require_csrf)])
async def upload_file(event_id: int, challenge_id: int, request: Request, content: bytes = Body(..., media_type="application/octet-stream"), actor: User = Depends(require_permission("challenge.update")), db: DbSession = Depends(get_db)) -> dict[str, object]:
    event = _get_event(db, actor, event_id)
    challenge = next((x for x in list_challenges(db, event, include_archived=True) if x.id == challenge_id), None)
    if challenge is None:
        raise HTTPException(404, "challenge not found")
    declared_size = request.headers.get("content-length")
    if declared_size and declared_size.isdigit() and int(declared_size) > MAX_FILE_SIZE:
        raise HTTPException(413, "file exceeds the 10 MB limit")
    if not content or len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "file must be between 1 byte and 10 MB")
    raw_name = unquote(request.headers.get("x-file-name", "attachment.txt")).replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", raw_name).strip(" .")[:180]
    if not name:
        raise HTTPException(422, "filename is invalid")
    content_type = _actual_file_type(content)
    storage_name = uuid4().hex
    root = Path(os.environ.get("CHALLENGE_FILE_STORAGE", "/app/storage/challenge-files")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    destination = (root / storage_name).resolve()
    if destination.parent != root:
        raise HTTPException(422, "filename is invalid")
    destination.write_bytes(content)
    file = ChallengeFile(public_id=str(uuid4()), challenge_id=challenge.id, original_name=name, storage_name=storage_name, content_type=content_type, size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest())
    db.add(file)
    audit.log(db, "CHALLENGE_FILE_UPLOADED", actor.id, "challenge", challenge.public_id, {"file": file.public_id, "size": file.size_bytes})
    db.commit()
    return _file_json(file)


@router.delete("/files/{file_public_id}", dependencies=[Depends(require_csrf)])
def delete_file(file_public_id: str, actor: User = Depends(require_permission("challenge.update")), db: DbSession = Depends(get_db)) -> dict[str, bool]:
    file = db.query(ChallengeFile).filter(ChallengeFile.public_id == file_public_id).first()
    if file is None:
        raise HTTPException(404, "file not found")
    challenge = db.get(Challenge, file.challenge_id)
    event = db.get(CtfEvent, challenge.event_id) if challenge else None
    if challenge is None or event is None or get_event(db, actor, event.id) is None:
        raise HTTPException(404, "file not found")
    root = Path(os.environ.get("CHALLENGE_FILE_STORAGE", "/app/storage/challenge-files")).resolve()
    path = (root / file.storage_name).resolve()
    if path.parent == root and path.is_file():
        path.unlink()
    db.delete(file)
    audit.log(db, "CHALLENGE_FILE_DELETED", actor.id, "challenge", challenge.public_id, {"file": file.public_id})
    db.commit()
    return {"ok": True}


@router.get("/files/{file_public_id}")
def download_file(file_public_id: str, principal: tuple[User, object] = Depends(current_session), db: DbSession = Depends(get_db)) -> FileResponse:
    actor = principal[0]
    file = db.query(ChallengeFile).filter(ChallengeFile.public_id == file_public_id).first()
    if file is None:
        raise HTTPException(404, "file not found")
    challenge = db.get(Challenge, file.challenge_id)
    if challenge is None or challenge.deleted_at is not None:
        raise HTTPException(404, "file not found")
    event = db.get(CtfEvent, challenge.event_id)
    if event is None:
        raise HTTPException(404, "file not found")
    roles = user_roles(actor)
    allowed = "ADMIN" in roles
    if "INSTRUCTOR" in roles:
        allowed = get_event(db, actor, event.id) is not None
    if "STUDENT" in roles:
        allowed = any(item.id == challenge.id for item in student_challenges(db, actor, event.public_id))
    if not allowed:
        raise HTTPException(404, "file not found")
    root = Path(os.environ.get("CHALLENGE_FILE_STORAGE", "/app/storage/challenge-files")).resolve()
    path = (root / file.storage_name).resolve()
    if path.parent != root or not path.is_file():
        raise HTTPException(404, "file not found")
    return FileResponse(path, media_type=file.content_type, filename=file.original_name)
