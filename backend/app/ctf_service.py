import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import selectinload

from app.models import (
    Category,
    Challenge,
    ChallengeFile,
    CtfEvent,
    Difficulty,
    Hint,
    SchoolClass,
    User,
    ctf_event_classes,
)
from app.users_service import user_roles


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _utc_naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value


def _admin(actor: User) -> bool:
    return "ADMIN" in user_roles(actor)


def categories(db: DbSession) -> list[Category]:
    return list(db.scalars(select(Category).order_by(Category.sort_order, Category.name)).all())


def difficulties(db: DbSession) -> list[Difficulty]:
    return list(db.scalars(select(Difficulty).order_by(Difficulty.sort_order, Difficulty.name)).all())


def save_taxonomy(db: DbSession, model: type[Category] | type[Difficulty], item_id: int | None, *, name: str, color: str, sort_order: int, multiplier: float) -> Category | Difficulty:
    if model is Category:
        item: Category | Difficulty | None = db.get(Category, item_id) if item_id is not None else Category()
    else:
        item = db.get(Difficulty, item_id) if item_id is not None else Difficulty()
    if item is None:
        raise LookupError("taxonomy item not found")
    item.name = name.strip()
    item.color = color.upper()
    item.sort_order = sort_order
    item.multiplier = multiplier
    db.add(item)
    db.flush()
    return item


def delete_taxonomy(db: DbSession, model: type[Category] | type[Difficulty], item_id: int) -> None:
    if model is Category:
        item: Category | Difficulty | None = db.get(Category, item_id)
    else:
        item = db.get(Difficulty, item_id)
    if item is None:
        raise LookupError("taxonomy item not found")
    if item.challenges:
        raise ValueError("taxonomy item is used by challenges")
    db.delete(item)


def _validated_scoring_config(strategy: str, config: dict[str, object] | None) -> dict[str, object]:
    values = config or {}
    allowed = {"FIXED": set(), "TIME_DECAY": {"window_seconds", "minimum_ratio"}, "DYNAMIC_BY_SOLVES": {"minimum_ratio", "decay_per_solve"}}[strategy]
    if set(values) - allowed:
        raise ValueError("scoring config contains unsupported settings")
    window = values.get("window_seconds", 1800)
    ratio = values.get("minimum_ratio", 0.2)
    decay = values.get("decay_per_solve", 0.05)
    if strategy == "TIME_DECAY" and (type(window) is not int or not 60 <= window <= 86400):
        raise ValueError("window_seconds must be between 60 and 86400")
    if strategy in {"TIME_DECAY", "DYNAMIC_BY_SOLVES"} and (isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or not 0.1 <= float(ratio) <= 1):
        raise ValueError("minimum_ratio must be between 0.1 and 1")
    if strategy == "DYNAMIC_BY_SOLVES" and (isinstance(decay, bool) or not isinstance(decay, (int, float)) or not 0 <= float(decay) <= 0.5):
        raise ValueError("decay_per_solve must be between 0 and 0.5")
    return dict(values)

def save_event(db: DbSession, actor: User, item_id: int | None, *, name: str, status: str, visibility: str, mode: str, rules_markdown: str, starts_at: datetime | None, ends_at: datetime | None, class_ids: list[int], scoring_strategy: str = "FIXED", scoring_config: dict[str, object] | None = None, max_attempts: int | None = None) -> CtfEvent:
    if scoring_strategy not in {"FIXED", "TIME_DECAY", "DYNAMIC_BY_SOLVES"}:
        raise ValueError("unsupported scoring strategy")
    scoring_config = _validated_scoring_config(scoring_strategy, scoring_config)
    if max_attempts is not None and not 1 <= max_attempts <= 1000:
        raise ValueError("max attempts must be between 1 and 1000")
    if ends_at and starts_at and ends_at <= starts_at:
        raise ValueError("event end must be later than start")
    classes = list(db.scalars(select(SchoolClass).where(SchoolClass.id.in_(set(class_ids)))).all()) if class_ids else []
    if len(classes) != len(set(class_ids)):
        raise ValueError("one or more classes were not found")
    if not _admin(actor) and any(item.teacher_user_id != actor.id for item in classes):
        raise PermissionError("you can only assign classes you teach")
    event = db.get(CtfEvent, item_id) if item_id is not None else CtfEvent(public_id=str(uuid4()))
    if event is None or event.deleted_at is not None:
        raise LookupError("event not found")
    event.name = name.strip()
    event.status = status
    event.visibility = visibility
    event.mode = mode
    event.rules_markdown = rules_markdown
    event.scoring_strategy = scoring_strategy
    event.scoring_config = scoring_config or {}
    event.max_attempts = max_attempts
    event.starts_at = _utc_naive(starts_at)
    event.ends_at = _utc_naive(ends_at)
    event.classes = classes
    db.add(event)
    db.flush()
    return event


def list_events(db: DbSession, actor: User, page: int, page_size: int, search: str | None) -> dict[str, object]:
    query = select(CtfEvent).options(selectinload(CtfEvent.classes)).where(CtfEvent.deleted_at.is_(None))
    if not _admin(actor):
        query = query.join(ctf_event_classes).join(SchoolClass).where(SchoolClass.teacher_user_id == actor.id)
    if search:
        query = query.where(CtfEvent.name.ilike(f"%{search.strip()}%"))
    query = query.distinct()
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    items = db.scalars(query.order_by(CtfEvent.created_at.desc(), CtfEvent.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def get_event(db: DbSession, actor: User, event_id: int) -> CtfEvent | None:
    query = select(CtfEvent).options(selectinload(CtfEvent.classes)).where(CtfEvent.id == event_id, CtfEvent.deleted_at.is_(None))
    event = db.scalar(query)
    if event is None or _admin(actor) or any(item.teacher_user_id == actor.id for item in event.classes):
        return event
    return None


def delete_event(event: CtfEvent) -> None:
    event.status = "ARCHIVED"
    event.deleted_at = _now()


def _check_prerequisites(db: DbSession, event_id: int, challenge_id: int | None, prerequisite_ids: list[int]) -> list[Challenge]:
    ids = set(prerequisite_ids)
    if challenge_id is not None and challenge_id in ids:
        raise ValueError("a challenge cannot require itself")
    if len(ids) != len(prerequisite_ids):
        raise ValueError("duplicate prerequisites are not allowed")
    required = list(db.scalars(select(Challenge).where(Challenge.id.in_(ids), Challenge.deleted_at.is_(None))).all()) if ids else []
    if len(required) != len(ids):
        raise ValueError("one or more prerequisites were not found")
    if any(item.event_id != event_id for item in required):
        raise ValueError("prerequisites must belong to the same event")
    if challenge_id is not None:
        graph = {item.id: [parent.id for parent in item.prerequisites] for item in db.scalars(select(Challenge).options(selectinload(Challenge.prerequisites))).all()}
        graph[challenge_id] = [item.id for item in required]
        def reaches(node: int, target: int, seen: set[int]) -> bool:
            if node == target:
                return True
            if node in seen:
                return False
            seen.add(node)
            return any(reaches(parent, target, seen) for parent in graph.get(node, []))
        if any(reaches(item.id, challenge_id, set()) for item in required):
            raise ValueError("challenge prerequisites cannot contain cycles")
    return required


def save_challenge(db: DbSession, event: CtfEvent, item_id: int | None, *, category_id: int, difficulty_id: int, slug: str, title: str, description_markdown: str, status: str, points: int, sort_order: int, delivery_type: str, delivery_config: dict[str, object], module_id: str | None, flag_hash: str | None = None, prerequisite_ids: list[int], scoring_strategy: str | None = None, scoring_config: dict[str, object] | None = None, max_attempts: int | None = None) -> Challenge:
    if scoring_strategy not in {None, "FIXED", "TIME_DECAY", "DYNAMIC_BY_SOLVES"}:
        raise ValueError("unsupported scoring strategy")
    scoring_config = _validated_scoring_config(scoring_strategy or event.scoring_strategy, scoring_config)
    if max_attempts is not None and not 1 <= max_attempts <= 1000:
        raise ValueError("max attempts must be between 1 and 1000")
    if delivery_type != "STATIC":
        raise ValueError("only STATIC delivery is implemented")
    category = db.get(Category, category_id)
    difficulty = db.get(Difficulty, difficulty_id)
    if category is None or difficulty is None:
        raise ValueError("category and difficulty are required")
    duplicate = db.scalar(select(Challenge.id).where(Challenge.event_id == event.id, Challenge.slug == slug, Challenge.deleted_at.is_(None), Challenge.id != (item_id or -1)))
    if duplicate is not None:
        raise ValueError("slug already exists in this event")
    item = db.get(Challenge, item_id) if item_id is not None else Challenge(public_id=str(uuid4()), event_id=event.id, slug=slug, title=title, category_id=category_id, difficulty_id=difficulty_id)
    if item is None or item.deleted_at is not None or item.event_id != event.id:
        raise LookupError("challenge not found in this event")
    item.category_id = category_id
    item.difficulty_id = difficulty_id
    item.slug = slug.strip().lower()
    item.title = title.strip()
    item.description_markdown = description_markdown
    item.status = status
    item.points = points
    item.sort_order = sort_order
    item.delivery_type = delivery_type
    item.delivery_config = delivery_config
    item.module_id = module_id
    item.flag_hash = flag_hash
    item.scoring_strategy = scoring_strategy
    item.scoring_config = scoring_config or {}
    item.max_attempts = max_attempts
    item.prerequisites = _check_prerequisites(db, event.id, item.id if item_id else None, prerequisite_ids)
    db.add(item)
    db.flush()
    return item


def list_challenges(db: DbSession, event: CtfEvent, *, include_archived: bool = False) -> list[Challenge]:
    query = select(Challenge).options(selectinload(Challenge.category), selectinload(Challenge.difficulty), selectinload(Challenge.prerequisites), selectinload(Challenge.files), selectinload(Challenge.hints)).where(Challenge.event_id == event.id, Challenge.deleted_at.is_(None))
    if not include_archived:
        query = query.where(Challenge.status != "ARCHIVED")
    return list(db.scalars(query.order_by(Challenge.sort_order, Challenge.id)).unique().all())


def soft_delete_challenge(item: Challenge) -> None:
    item.deleted_at = _now()
    item.status = "ARCHIVED"


def create_hint(db: DbSession, challenge: Challenge, *, order: int, cost: int, content_markdown: str) -> Hint:
    if db.scalar(select(Hint.id).where(Hint.challenge_id == challenge.id, Hint.order == order)) is not None:
        raise ValueError("hint order already exists")
    hint = Hint(challenge_id=challenge.id, order=order, cost=cost, content_markdown=content_markdown)
    db.add(hint)
    db.flush()
    return hint


def update_hint(db: DbSession, hint: Hint, *, order: int, cost: int, content_markdown: str) -> Hint:
    duplicate = db.scalar(select(Hint.id).where(Hint.challenge_id == hint.challenge_id, Hint.order == order, Hint.id != hint.id))
    if duplicate is not None:
        raise ValueError("hint order already exists")
    hint.order = order
    hint.cost = cost
    hint.content_markdown = content_markdown
    return hint


def _copy_files(db: DbSession, source: Challenge, target: Challenge) -> None:
    root = Path(os.environ.get("CHALLENGE_FILE_STORAGE", "/app/storage/challenge-files")).resolve()
    for original in source.files:
        source_path = (root / original.storage_name).resolve()
        if source_path.parent != root or not source_path.is_file():
            continue
        storage_name = uuid4().hex
        shutil.copyfile(source_path, root / storage_name)
        db.add(ChallengeFile(public_id=str(uuid4()), challenge=target, original_name=original.original_name, storage_name=storage_name, content_type=original.content_type, size_bytes=original.size_bytes, sha256=original.sha256))


def duplicate_challenge(db: DbSession, event: CtfEvent, source: Challenge) -> Challenge:
    slug = f"{source.slug[:88]}-copy-{uuid4().hex[:8]}"
    item = save_challenge(db, event, None, category_id=source.category_id, difficulty_id=source.difficulty_id, slug=slug, title=f"Copy of {source.title}"[:180], description_markdown=source.description_markdown, status="DRAFT", points=source.points, sort_order=source.sort_order, delivery_type=source.delivery_type, delivery_config=dict(source.delivery_config), module_id=source.module_id, flag_hash=source.flag_hash, prerequisite_ids=[x.id for x in source.prerequisites], scoring_strategy=source.scoring_strategy, scoring_config=dict(source.scoring_config), max_attempts=source.max_attempts)
    for hint in source.hints:
        create_hint(db, item, order=hint.order, cost=hint.cost, content_markdown=hint.content_markdown)
    _copy_files(db, source, item)
    db.flush()
    return item


def duplicate_event(db: DbSession, actor: User, source: CtfEvent) -> CtfEvent:
    item = save_event(db, actor, None, name=f"Copy of {source.name}"[:160], status="DRAFT", visibility=source.visibility, mode=source.mode, rules_markdown=source.rules_markdown, starts_at=source.starts_at, ends_at=source.ends_at, class_ids=[x.id for x in source.classes], scoring_strategy=source.scoring_strategy, scoring_config=dict(source.scoring_config), max_attempts=source.max_attempts)
    source_challenges = list_challenges(db, source, include_archived=True)
    clones = {challenge.id: duplicate_challenge(db, item, challenge) for challenge in source_challenges if challenge.deleted_at is None}
    for challenge in source_challenges:
        target = clones.get(challenge.id)
        if target is not None:
            target.prerequisites = [clones[parent.id] for parent in challenge.prerequisites if parent.id in clones]
    db.flush()
    return item


def student_events(db: DbSession, actor: User) -> list[CtfEvent]:
    now = _now()
    class_ids = [item.id for item in actor.enrolled_classes]
    access = CtfEvent.visibility == "PUBLIC"
    if class_ids:
        access = or_(access, CtfEvent.id.in_(select(ctf_event_classes.c.event_id).where(ctf_event_classes.c.class_id.in_(class_ids))))
    return list(db.scalars(select(CtfEvent).where(access, CtfEvent.status == "PUBLISHED", CtfEvent.deleted_at.is_(None), or_(CtfEvent.starts_at.is_(None), CtfEvent.starts_at <= now), or_(CtfEvent.ends_at.is_(None), CtfEvent.ends_at > now)).order_by(CtfEvent.starts_at)).all())


def student_challenges(db: DbSession, actor: User, event_public_id: str, completed_ids: set[int] | None = None) -> list[Challenge]:
    event_ids = {item.id for item in student_events(db, actor)}
    event = db.scalar(select(CtfEvent).where(CtfEvent.public_id == event_public_id, CtfEvent.id.in_(event_ids)))
    if event is None:
        return []
    if completed_ids is None:
        from app.models import ChallengeProgress
        completed_ids = set(db.scalars(select(ChallengeProgress.challenge_id).where(ChallengeProgress.user_id == actor.id, ChallengeProgress.completed_at.is_not(None))).all())
    completed = completed_ids
    items = list_challenges(db, event)
    return [item for item in items if item.status == "PUBLISHED" and all(parent.id in completed for parent in item.prerequisites)]
