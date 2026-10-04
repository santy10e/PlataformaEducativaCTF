import hashlib
import io
import stat
import zipfile

import pytest
import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.challenge_import_service import (
    ImportValidationError,
    export_challenge,
    export_event,
    import_package,
    parse_package,
    preview_json,
)
from app.ctf_service import save_event, save_taxonomy
from app.models import (
    Category,
    Challenge,
    ChallengeFile,
    ChallengeFlag,
    CtfEvent,
    Difficulty,
    Hint,
    Role,
    User,
)


def make_user(db: DbSession, username: str) -> User:
    role = db.scalar(select(Role).where(Role.name == "ADMIN"))
    if role is None:
        role = Role(name="ADMIN", is_system=True)
        db.add(role)
        db.flush()
    user = User(username=username, password_hash="unused", display_name=username, is_active=True, roles=[role])
    db.add(user)
    db.flush()
    return user


def make_target(db: DbSession) -> tuple[User, CtfEvent]:
    admin = make_user(db, "package_admin")
    event = save_event(db, admin, None, name="Import destination", status="DRAFT", visibility="ASSIGNED",
        mode="JEOPARDY", rules_markdown="", starts_at=None, ends_at=None, class_ids=[])
    save_taxonomy(db, Category, None, name="Web", color="#142550", sort_order=0, multiplier=1)
    save_taxonomy(db, Difficulty, None, name="Inicial", color="#1BAEC3", sort_order=0, multiplier=1)
    db.flush()
    return admin, event


def package_bytes(slug: str = "header-trace", title: str = "Header trace", *, include_file: bool = True) -> bytes:
    manifest = {
        "format_version": 1,
        "slug": slug,
        "title": title,
        "category": "Web",
        "difficulty": "Inicial",
        "description_markdown": "Busca el encabezado oculto, con tilde: señal.",
        "points": 125,
        "flags": [{"strategy": "STATIC", "value": "CYBERLAB{sample_flag}"}],
        "hints": [{"content_markdown": "Mira el encabezado X-Lab.", "cost": 5}],
        "files": ([{"path": "files/evidence.txt", "name": "evidencia.txt", "content_type": "text/plain"}] if include_file else []),
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("ctf.yml", yaml.safe_dump({"format_version": 1, "name": "Práctica", "challenges": [f"{slug}/challenge.yml"]}, allow_unicode=True))
        archive.writestr(f"{slug}/challenge.yml", yaml.safe_dump(manifest, allow_unicode=True))
        if include_file:
            archive.writestr(f"{slug}/files/evidence.txt", "Evidencia de prueba con ñ y coma, incluida.\n")
    return output.getvalue()


def test_preview_import_is_idempotent_and_stores_attachments_and_flags(db: DbSession, tmp_path) -> None:
    _, event = make_target(db)
    content = package_bytes()

    parsed = parse_package(db, event, content)
    preview = preview_json(parsed)
    assert preview["valid"] is True
    assert preview["challenges"][0]["status_after_import"] == "DRAFT"
    first = import_package(db, event, parsed, str(tmp_path))
    db.commit()
    challenge_id = first["challenges"][0]["id"]
    challenge = db.get(Challenge, challenge_id)
    assert challenge is not None and challenge.status == "DRAFT"
    assert challenge.title == "Header trace"
    assert challenge.hints[0].content_markdown == "Mira el encabezado X-Lab."
    assert challenge.files[0].original_name == "evidencia.txt"
    assert (tmp_path / challenge.files[0].storage_name).read_text(encoding="utf-8").startswith("Evidencia")
    flag = db.scalar(select(ChallengeFlag).where(ChallengeFlag.challenge_id == challenge_id))
    assert flag is not None and flag.matcher == hashlib.sha256(b"CYBERLAB{sample_flag}").hexdigest()

    second = import_package(db, event, parse_package(db, event, content), str(tmp_path))
    db.commit()
    assert second["created"] == 0 and second["updated"] == 1
    assert second["challenges"][0]["id"] == challenge_id
    assert len(list(db.scalars(select(Hint).where(Hint.challenge_id == challenge_id)).all())) == 1
    assert len(list(db.scalars(select(ChallengeFile).where(ChallengeFile.challenge_id == challenge_id)).all())) == 1


def test_export_import_roundtrip_preserves_challenge_content_without_plaintext_flag(db: DbSession, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, event = make_target(db)
    monkeypatch.setenv("CHALLENGE_FILE_STORAGE", str(tmp_path))
    result = import_package(db, event, parse_package(db, event, package_bytes()), str(tmp_path))
    db.commit()
    original = db.get(Challenge, result["challenges"][0]["id"])
    assert original is not None

    exported = export_challenge(db, original)
    round_trip = parse_package(db, event, exported)
    manifest = round_trip.challenges[0].manifest
    assert manifest.slug == original.slug
    assert manifest.title == original.title
    assert manifest.description_markdown == original.description_markdown
    assert manifest.flags[0].matcher_sha256 == hashlib.sha256(b"CYBERLAB{sample_flag}").hexdigest()
    assert round_trip.challenges[0].files[0][1] == b"Evidencia de prueba con \xc3\xb1 y coma, incluida.\n"

    event_package = parse_package(db, event, export_event(db, event, [original]))
    assert event_package.name == event.name
    assert event_package.challenges[0].manifest.slug == original.slug


@pytest.mark.parametrize("path", ["../escape.txt", "/absolute.txt", "C:/absolute.txt", "safe/../../escape.txt"])
def test_zip_slip_and_absolute_paths_are_rejected(path: str) -> None:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(path, b"unsafe")
    with pytest.raises(ImportValidationError, match="validation"):
        parse_package(DbSession(), CtfEvent(id=1), output.getvalue())


def test_symlinks_and_zip_bombs_are_rejected() -> None:
    symlink = io.BytesIO()
    with zipfile.ZipFile(symlink, "w") as archive:
        info = zipfile.ZipInfo("linked/challenge.yml")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, "../../outside")
    with pytest.raises(ImportValidationError):
        from app.challenge_import_service import _read_archive
        _read_archive(symlink.getvalue())

    bomb = io.BytesIO()
    with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("oversized.txt", b"0" * (2 * 1024 * 1024))
    with pytest.raises(ImportValidationError, match="validation"):
        from app.challenge_import_service import _read_archive
        _read_archive(bomb.getvalue())


def test_invalid_manifest_reports_file_and_field(db: DbSession) -> None:
    _, event = make_target(db)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("challenge.yml", "format_version: 99\nslug: Bad Slug\n")
    with pytest.raises(ImportValidationError) as error:
        parse_package(db, event, output.getvalue())
    assert error.value.errors
    assert all(row["file"] == "challenge.yml" for row in error.value.errors)
