"""Safe, deterministic ZIP import/export for challenge manifests."""

from __future__ import annotations

import hashlib
import io
import re
import stat
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Literal
from uuid import uuid4

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from yaml.events import AliasEvent  # type: ignore[import-untyped]

from app.models import Category, Challenge, ChallengeFile, ChallengeFlag, CtfEvent, Difficulty, Hint
from app.scoring_service import add_flag, validate_regex

MAX_ARCHIVE_BYTES = 20 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 1000
MAX_TOTAL_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_MEMBER_BYTES = 10 * 1024 * 1024
MAX_MANIFEST_BYTES = 128 * 1024
MAX_COMPRESSION_RATIO = 200


class NoAliasSafeLoader(yaml.SafeLoader):  # type: ignore[misc]
    def compose_node(self, parent: Any, index: Any) -> Any:
        if self.check_event(AliasEvent):
            raise yaml.YAMLError("YAML aliases are not allowed")
        return super().compose_node(parent, index)


def _mapping(loader: NoAliasSafeLoader, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise yaml.YAMLError(f"duplicate manifest key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


NoAliasSafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HintManifest(StrictModel):
    content_markdown: str = Field(min_length=1, max_length=10000)
    cost: int = Field(default=0, ge=0, le=100000)


class FlagManifest(StrictModel):
    strategy: Literal["STATIC", "REGEX", "DYNAMIC_HMAC"]
    value: str | None = Field(default=None, min_length=1, max_length=256)
    pattern: str | None = Field(default=None, min_length=1, max_length=256)
    format: str | None = Field(default=None, min_length=1, max_length=255)
    matcher_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class FileManifest(StrictModel):
    path: str = Field(min_length=1, max_length=240)
    name: str | None = Field(default=None, min_length=1, max_length=180)
    content_type: str | None = Field(default=None, max_length=120)

    @field_validator("name")
    @classmethod
    def safe_display_name(cls, value: str | None) -> str | None:
        if value is not None and ("/" in value or "\\" in value or value in {".", ".."} or any(ord(char) < 32 for char in value)):
            raise ValueError("attachment name must be a plain filename")
        return value


class ChallengeManifest(StrictModel):
    format_version: Literal[1] = 1
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: str = Field(min_length=2, max_length=180)
    category: str = Field(min_length=1, max_length=80)
    difficulty: str = Field(min_length=1, max_length=48)
    description_markdown: str = Field(default="", max_length=50000)
    points: int = Field(default=100, ge=1, le=100000)
    sort_order: int = Field(default=0, ge=0, le=10000)
    module_id: str | None = Field(default=None, max_length=100)
    delivery_config: dict[str, Any] = Field(default_factory=dict)
    scoring_strategy: Literal["FIXED", "TIME_DECAY", "DYNAMIC_BY_SOLVES"] | None = None
    scoring_config: dict[str, Any] = Field(default_factory=dict)
    max_attempts: int | None = Field(default=None, ge=1, le=1000)
    prerequisites: list[str] = Field(default_factory=list, max_length=100)
    hints: list[HintManifest] = Field(default_factory=list, max_length=100)
    flags: list[FlagManifest] = Field(default_factory=list, max_length=20)
    files: list[FileManifest] = Field(default_factory=list, max_length=100)


class CtfManifest(StrictModel):
    format_version: Literal[1] = 1
    name: str = Field(min_length=2, max_length=160)
    challenges: list[str] = Field(min_length=1, max_length=500)

    @field_validator("challenges")
    @classmethod
    def unique_challenge_paths(cls, paths: list[str]) -> list[str]:
        if len(set(paths)) != len(paths):
            raise ValueError("challenge manifest paths must be unique")
        return paths


@dataclass(frozen=True)
class PackageChallenge:
    manifest_path: str
    manifest: ChallengeManifest
    files: list[tuple[FileManifest, bytes]]
    category: Category
    difficulty: Difficulty
    existing: Challenge | None
    prerequisites: list[Challenge]


@dataclass(frozen=True)
class ChallengePackage:
    name: str
    challenges: list[PackageChallenge]
    warnings: list[dict[str, str]]


class ImportValidationError(ValueError):
    def __init__(self, errors: list[dict[str, str]], warnings: list[dict[str, str]] | None = None) -> None:
        super().__init__("challenge package validation failed")
        self.errors = errors
        self.warnings = warnings or []


def _safe_member(name: str) -> bool:
    if not name or "\\" in name or "\x00" in name or name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        return False
    parts = name.split("/")
    return bool(parts) and all(part not in {"", ".", ".."} for part in parts)


def _attachment_type(content: bytes) -> str | None:
    signatures = ((b"%PDF-", "application/pdf"), (b"\x89PNG\r\n\x1a\n", "image/png"),
        (b"\xff\xd8\xff", "image/jpeg"), (b"GIF87a", "image/gif"), (b"GIF89a", "image/gif"),
        (b"PK\x03\x04", "application/zip"))
    for signature, media_type in signatures:
        if content.startswith(signature):
            return media_type
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return None if b"\x00" in content else "text/plain"


def _read_archive(content: bytes) -> dict[str, bytes]:
    if not content or len(content) > MAX_ARCHIVE_BYTES:
        raise ImportValidationError([{"file": "", "field": "archive", "message": "ZIP must be between 1 byte and 20 MB"}])
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except (zipfile.BadZipFile, OSError) as exc:
        raise ImportValidationError([{"file": "", "field": "archive", "message": "file is not a valid ZIP archive"}]) from exc
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_ARCHIVE_MEMBERS:
            raise ImportValidationError([{"file": "", "field": "archive", "message": "ZIP contains more than 1000 entries"}])
        total = 0
        entries: dict[str, bytes] = {}
        errors: list[dict[str, str]] = []
        for info in infos:
            name = info.filename.rstrip("/") if info.is_dir() else info.filename
            if not _safe_member(name):
                errors.append({"file": info.filename[:240], "field": "path", "message": "unsafe or absolute ZIP path"})
                continue
            if info.is_dir():
                continue
            if info.flag_bits & 0x1:
                errors.append({"file": name, "field": "archive", "message": "encrypted ZIP entries are not supported"})
                continue
            mode = (info.external_attr >> 16) & 0o170000
            if mode == stat.S_IFLNK:
                errors.append({"file": name, "field": "path", "message": "symbolic links are not allowed"})
                continue
            if name in entries:
                errors.append({"file": name, "field": "path", "message": "duplicate ZIP path"})
                continue
            if info.file_size > MAX_MEMBER_BYTES:
                errors.append({"file": name, "field": "size", "message": "each file must be 10 MB or smaller"})
                continue
            total += info.file_size
            if total > MAX_TOTAL_UNCOMPRESSED_BYTES:
                errors.append({"file": name, "field": "size", "message": "expanded ZIP contents exceed 50 MB"})
                break
            if info.file_size > 1024 * 1024 and (not info.compress_size or info.file_size / info.compress_size > MAX_COMPRESSION_RATIO):
                errors.append({"file": name, "field": "compression", "message": "compression ratio exceeds the allowed limit"})
                continue
            try:
                data = archive.read(info)
            except (zipfile.BadZipFile, RuntimeError, OSError):
                errors.append({"file": name, "field": "archive", "message": "ZIP entry cannot be read"})
                continue
            if len(data) != info.file_size:
                errors.append({"file": name, "field": "size", "message": "ZIP entry size did not match its directory record"})
                continue
            entries[name] = data
        if errors:
            raise ImportValidationError(errors)
        return entries


def _yaml(data: bytes, file_name: str) -> dict[str, Any]:
    if len(data) > MAX_MANIFEST_BYTES:
        raise ImportValidationError([{"file": file_name, "field": "size", "message": "manifest exceeds 128 KB"}])
    try:
        value = yaml.load(data.decode("utf-8-sig"), Loader=NoAliasSafeLoader)
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ImportValidationError([{"file": file_name, "field": "yaml", "message": f"invalid or unsafe YAML: {str(exc)[:180]}"}]) from exc
    if not isinstance(value, dict):
        raise ImportValidationError([{"file": file_name, "field": "manifest", "message": "manifest root must be a mapping"}])
    return value


def _model(model_type: type[BaseModel], raw: dict[str, Any], path: str) -> BaseModel:
    try:
        return model_type.model_validate(raw)
    except ValidationError as exc:
        errors = [{"file": path, "field": ".".join(str(part) for part in item["loc"]), "message": item["msg"]} for item in exc.errors()]
        raise ImportValidationError(errors) from exc


def parse_package(db: Session, event: CtfEvent, content: bytes) -> ChallengePackage:
    entries = _read_archive(content)
    warnings: list[dict[str, str]] = []
    ctf_path = "ctf.yml"
    if ctf_path in entries:
        ctf = _model(CtfManifest, _yaml(entries[ctf_path], ctf_path), ctf_path)
        assert isinstance(ctf, CtfManifest)
        name, manifest_paths = ctf.name, ctf.challenges
    else:
        manifest_paths = sorted(path for path in entries if PurePosixPath(path).name == "challenge.yml")
        if len(manifest_paths) != 1:
            raise ImportValidationError([{"file": "", "field": "ctf.yml", "message": "include ctf.yml, or exactly one challenge.yml for a single-challenge package"}])
        name = "Retos importados"

    manifests: list[tuple[str, ChallengeManifest]] = []
    errors: list[dict[str, str]] = []
    for manifest_path in manifest_paths:
        if not _safe_member(manifest_path) or PurePosixPath(manifest_path).name != "challenge.yml":
            errors.append({"file": manifest_path[:240], "field": "challenges", "message": "each entry must reference a safe challenge.yml path"})
            continue
        raw = entries.get(manifest_path)
        if raw is None:
            errors.append({"file": manifest_path, "field": "challenges", "message": "referenced manifest is missing from ZIP"})
            continue
        try:
            manifest = _model(ChallengeManifest, _yaml(raw, manifest_path), manifest_path)
            assert isinstance(manifest, ChallengeManifest)
            manifests.append((manifest_path, manifest))
        except ImportValidationError as exc:
            errors.extend(exc.errors)
    if errors:
        raise ImportValidationError(errors)
    slugs = [manifest.slug for _, manifest in manifests]
    if len(set(slugs)) != len(slugs):
        raise ImportValidationError([{"file": "ctf.yml", "field": "challenges", "message": "challenge slugs must be unique within a package"}])

    event_challenges = list(db.scalars(select(Challenge).where(Challenge.event_id == event.id, Challenge.deleted_at.is_(None))).all())
    existing_by_slug = {item.slug: item for item in event_challenges}
    categories = {row.name.casefold(): row for row in db.scalars(select(Category)).all()}
    difficulties = {row.name.casefold(): row for row in db.scalars(select(Difficulty)).all()}
    package_slugs = set(slugs)
    referenced_paths = {"ctf.yml"} if ctf_path in entries else set()
    referenced_paths.update(path for path, _ in manifests)
    parsed: list[PackageChallenge] = []
    errors = []

    for path, manifest in manifests:
        category = categories.get(manifest.category.casefold())
        difficulty = difficulties.get(manifest.difficulty.casefold())
        if category is None:
            errors.append({"file": path, "field": "category", "message": f"unknown category: {manifest.category}"})
        if difficulty is None:
            errors.append({"file": path, "field": "difficulty", "message": f"unknown difficulty: {manifest.difficulty}"})
        existing = existing_by_slug.get(manifest.slug)
        if existing is not None:
            warnings.append({"file": path, "field": "slug", "message": "matching slug will update the existing challenge"})
        files: list[tuple[FileManifest, bytes]] = []
        manifest_dir = PurePosixPath(path).parent
        for file_meta in manifest.files:
            stored_path = f"{manifest_dir.as_posix()}/{file_meta.path}" if manifest_dir.as_posix() != "." else file_meta.path
            if not _safe_member(file_meta.path) or not _safe_member(stored_path):
                errors.append({"file": path, "field": "files.path", "message": f"unsafe attachment path: {file_meta.path}"})
                continue
            file_data = entries.get(stored_path)
            if file_data is None:
                errors.append({"file": path, "field": "files.path", "message": f"attachment is missing: {file_meta.path}"})
                continue
            actual_type = _attachment_type(file_data)
            if actual_type is None:
                errors.append({"file": path, "field": "files.path", "message": f"unsupported attachment content: {file_meta.path}"})
                continue
            if file_meta.content_type and file_meta.content_type != actual_type:
                warnings.append({"file": path, "field": "files.content_type", "message": f"declared type for {file_meta.path} did not match its content; detected type will be used"})
            referenced_paths.add(stored_path)
            files.append((file_meta, file_data))
        prereqs: list[Challenge] = []
        if len(set(manifest.prerequisites)) != len(manifest.prerequisites):
            errors.append({"file": path, "field": "prerequisites", "message": "prerequisite slugs must be unique"})
        for prerequisite_slug in manifest.prerequisites:
            if prerequisite_slug == manifest.slug:
                errors.append({"file": path, "field": "prerequisites", "message": "challenge cannot require itself"})
            elif prerequisite_slug not in package_slugs and prerequisite_slug not in existing_by_slug:
                errors.append({"file": path, "field": "prerequisites", "message": f"unknown prerequisite slug: {prerequisite_slug}"})
            elif prerequisite_slug not in package_slugs:
                prereq = existing_by_slug[prerequisite_slug]
                if prereq not in prereqs:
                    prereqs.append(prereq)
        for flag in manifest.flags:
            if flag.strategy == "STATIC":
                if bool(flag.value) == bool(flag.matcher_sha256) or flag.pattern is not None or flag.format is not None:
                    errors.append({"file": path, "field": "flags", "message": "static flag needs exactly one of value or matcher_sha256"})
            elif flag.strategy == "REGEX":
                if flag.pattern is None or flag.value is not None or flag.matcher_sha256 is not None or flag.format is not None:
                    errors.append({"file": path, "field": "flags", "message": "regex flag needs pattern only"})
                else:
                    try:
                        validate_regex(flag.pattern)
                    except ValueError as exc:
                        errors.append({"file": path, "field": "flags.pattern", "message": str(exc)})
            elif flag.format is None or "{digest}" not in flag.format or flag.value is not None or flag.pattern is not None or flag.matcher_sha256 is not None:
                errors.append({"file": path, "field": "flags", "message": "dynamic flag requires format containing {digest}"})
        if category is not None and difficulty is not None:
            parsed.append(PackageChallenge(path, manifest, files, category, difficulty, existing, prereqs))

    graph = {row.slug: [item.slug for item in row.prerequisites] for row in event_challenges}
    graph.update({manifest.slug: manifest.prerequisites for _, manifest in manifests})
    visiting: set[str] = set()
    visited: set[str] = set()

    def has_cycle(slug: str) -> bool:
        if slug in visiting:
            return True
        if slug in visited:
            return False
        visiting.add(slug)
        cyclic = any(has_cycle(parent) for parent in graph.get(slug, []) if parent in graph)
        visiting.remove(slug)
        visited.add(slug)
        return cyclic

    if any(has_cycle(slug) for slug in graph):
        errors.append({"file": "", "field": "prerequisites", "message": "prerequisites cannot contain cycles"})
    for unreferenced in sorted(set(entries) - referenced_paths):
        warnings.append({"file": unreferenced, "field": "path", "message": "file is not referenced by a challenge manifest and will be ignored"})

    if errors:
        raise ImportValidationError(errors, warnings)
    return ChallengePackage(name, parsed, warnings)


def preview_json(package: ChallengePackage) -> dict[str, Any]:
    return {"valid": True, "name": package.name, "count": len(package.challenges), "warnings": package.warnings,
        "challenges": [{"manifest": row.manifest_path, "slug": row.manifest.slug, "title": row.manifest.title,
            "category": row.category.name, "difficulty": row.difficulty.name, "points": row.manifest.points,
            "status_after_import": "DRAFT", "action": "update" if row.existing else "create",
            "hints": len(row.manifest.hints), "files": len(row.files)} for row in package.challenges]}


def import_package(db: Session, event: CtfEvent, package: ChallengePackage, storage_root: str) -> dict[str, Any]:
    from pathlib import Path

    from app.ctf_service import save_challenge

    root = Path(storage_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    existing_challenges = list(db.scalars(select(Challenge).where(Challenge.event_id == event.id, Challenge.deleted_at.is_(None))).all())
    by_slug = {item.slug: item for item in existing_challenges}
    imported: dict[str, Challenge] = {}
    obsolete_storage_names: list[str] = []
    new_storage_names: list[str] = []
    for row in package.challenges:
        manifest = row.manifest
        existing = by_slug.get(manifest.slug)
        item = save_challenge(db, event, existing.id if existing is not None else None,
            category_id=row.category.id, difficulty_id=row.difficulty.id, slug=manifest.slug, title=manifest.title,
            description_markdown=manifest.description_markdown, status="DRAFT", points=manifest.points,
            sort_order=manifest.sort_order, delivery_type="STATIC", delivery_config=manifest.delivery_config,
            module_id=manifest.module_id, prerequisite_ids=[], scoring_strategy=manifest.scoring_strategy,
            scoring_config=manifest.scoring_config, max_attempts=manifest.max_attempts)
        item.prerequisites = []
        imported[manifest.slug] = item
        db.flush()

    for row in package.challenges:
        item = imported[row.manifest.slug]
        prerequisite_items = [imported.get(slug) or by_slug[slug] for slug in row.manifest.prerequisites]
        item.prerequisites = prerequisite_items
        db.flush()
        for old_hint in list(item.hints):
            db.delete(old_hint)
        db.flush()
        for order, hint in enumerate(row.manifest.hints):
            db.add(Hint(challenge_id=item.id, order=order, cost=hint.cost, content_markdown=hint.content_markdown))
        for old_flag in list(db.scalars(select(ChallengeFlag).where(ChallengeFlag.challenge_id == item.id)).all()):
            db.delete(old_flag)
        for flag in row.manifest.flags:
            if flag.strategy == "STATIC" and flag.matcher_sha256:
                db.add(ChallengeFlag(challenge_id=item.id, strategy="STATIC", matcher=flag.matcher_sha256, flag_format=None))
            elif flag.strategy == "STATIC":
                add_flag(db, item, "STATIC", flag.value, None)
            elif flag.strategy == "REGEX":
                add_flag(db, item, "REGEX", flag.pattern, None)
            else:
                add_flag(db, item, "DYNAMIC_HMAC", None, flag.format)
        for old_file in list(item.files):
            obsolete_storage_names.append(old_file.storage_name)
            db.delete(old_file)
        db.flush()
        for file_meta, data in row.files:
            storage_name = uuid4().hex
            (root / storage_name).write_bytes(data)
            new_storage_names.append(storage_name)
            db.add(ChallengeFile(public_id=str(uuid4()), challenge_id=item.id,
                original_name=(file_meta.name or PurePosixPath(file_meta.path).name)[:180], storage_name=storage_name,
                content_type=_attachment_type(data) or "application/octet-stream", size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    db.flush()
    return {"created": sum(1 for row in package.challenges if row.manifest.slug not in by_slug),
        "updated": sum(1 for row in package.challenges if row.manifest.slug in by_slug),
        "_obsolete_storage_names": obsolete_storage_names,
        "_new_storage_names": new_storage_names,
        "challenges": [{"id": imported[row.manifest.slug].id, "slug": row.manifest.slug, "title": row.manifest.title, "status": "DRAFT"} for row in package.challenges]}


def export_challenge(db: Session, challenge: Challenge) -> bytes:
    import os
    from pathlib import Path

    files: list[dict[str, str]] = []
    payloads: dict[str, bytes] = {}
    root = Path(os.environ.get("CHALLENGE_FILE_STORAGE", "/app/storage/challenge-files")).resolve()
    for item in challenge.files:
        source = (root / item.storage_name).resolve()
        if source.parent == root and source.is_file():
            relative = f"files/{item.original_name}"
            files.append({"path": relative, "name": item.original_name, "content_type": item.content_type})
            payloads[relative] = source.read_bytes()
    flags = []
    for flag in db.scalars(select(ChallengeFlag).where(ChallengeFlag.challenge_id == challenge.id, ChallengeFlag.enabled.is_(True)).order_by(ChallengeFlag.id)).all():
        if flag.strategy == "STATIC" and flag.matcher:
            flags.append({"strategy": "STATIC", "matcher_sha256": flag.matcher})
        elif flag.strategy == "REGEX" and flag.matcher:
            flags.append({"strategy": "REGEX", "pattern": flag.matcher})
        elif flag.strategy == "DYNAMIC_HMAC" and flag.flag_format:
            flags.append({"strategy": "DYNAMIC_HMAC", "format": flag.flag_format})
    manifest = {"format_version": 1, "slug": challenge.slug, "title": challenge.title,
        "category": challenge.category.name, "difficulty": challenge.difficulty.name,
        "description_markdown": challenge.description_markdown, "points": challenge.points,
        "sort_order": challenge.sort_order, "module_id": challenge.module_id,
        "delivery_config": challenge.delivery_config, "scoring_strategy": challenge.scoring_strategy,
        "scoring_config": challenge.scoring_config, "max_attempts": challenge.max_attempts,
        "prerequisites": [item.slug for item in challenge.prerequisites],
        "hints": [{"content_markdown": item.content_markdown, "cost": item.cost} for item in challenge.hints],
        "flags": flags, "files": files}
    base = f"{challenge.slug}/"
    entries = {base + "challenge.yml": yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False).encode("utf-8")}
    entries.update({base + path: body for path, body in payloads.items()})
    return _zip_bytes(entries)


def export_event(db: Session, event: CtfEvent, challenges: list[Challenge]) -> bytes:
    refs = [f"{item.slug}/challenge.yml" for item in challenges]
    entries: dict[str, bytes] = {"ctf.yml": yaml.safe_dump({"format_version": 1, "name": event.name, "challenges": refs}, allow_unicode=True, sort_keys=False).encode("utf-8")}
    for item in challenges:
        with zipfile.ZipFile(io.BytesIO(export_challenge(db, item))) as challenge_zip:
            entries.update({info.filename: challenge_zip.read(info) for info in challenge_zip.infolist()})
    return _zip_bytes(entries)


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name in sorted(entries):
            if not _safe_member(name):
                raise ValueError("unsafe internal export path")
            archive.writestr(name, entries[name])
    return output.getvalue()
