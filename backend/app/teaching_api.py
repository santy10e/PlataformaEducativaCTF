import csv
from datetime import datetime
from io import BytesIO, StringIO
from typing import Any
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session as DbSession

from app import audit
from app.dependencies import get_db, require_csrf, require_permission
from app.models import Announcement, User
from app.teaching_service import analytics as get_analytics
from app.teaching_service import archive_announcement as archive_announcement_service
from app.teaching_service import close_event as close_event_service
from app.teaching_service import create_announcement as create_announcement_service
from app.teaching_service import list_announcements
from app.teaching_service import live_class as get_live_class
from app.teaching_service import student_announcements as get_student_announcements
from app.teaching_service import student_detail as get_student_detail

router = APIRouter(prefix="/api/v1/teaching", tags=["teaching"])


@router.get("/student/announcements")
def student_announcements(actor: User = Depends(require_permission("challenge.submit")), db: DbSession = Depends(get_db)) -> list[dict[str, object]]:
    return [{"id": row.id, "title": row.title, "content_markdown": row.content_markdown, "publish_at": row.publish_at} for row in get_student_announcements(db, actor)]


class AnnouncementInput(BaseModel):
    class_id: int | None = Field(default=None, ge=1)
    event_id: int | None = Field(default=None, ge=1)
    title: str = Field(min_length=2, max_length=180)
    content_markdown: str = Field(min_length=1, max_length=10000)
    publish_at: datetime | None = None

    @model_validator(mode="after")
    def one_scope(self) -> "AnnouncementInput":
        if (self.class_id is None) == (self.event_id is None):
            raise ValueError("select exactly one class or event")
        return self


@router.get("/analytics")
def analytics(class_id: int | None = None, event_id: int | None = None, student_id: int | None = None,
              date_from: datetime | None = None, date_to: datetime | None = None,
              grade_scale_id: int | None = None,
              actor: User = Depends(require_permission("event.manage")), db: DbSession = Depends(get_db)) -> dict[str, Any]:
    return get_analytics(db, actor, class_id=class_id, event_id=event_id, student_id=student_id,
                         date_from=date_from, date_to=date_to, grade_scale_id=grade_scale_id)


@router.get("/live")
def live_class(class_id: int | None = None, event_id: int | None = None,
               actor: User = Depends(require_permission("event.manage")), db: DbSession = Depends(get_db)) -> dict[str, Any]:
    return get_live_class(db, actor, class_id=class_id, event_id=event_id)


@router.get("/students/{student_id}")
def student_detail(student_id: int, class_id: int | None = None, event_id: int | None = None,
                   actor: User = Depends(require_permission("event.manage")), db: DbSession = Depends(get_db)) -> dict[str, Any]:
    return get_student_detail(db, actor, student_id=student_id, class_id=class_id, event_id=event_id)


@router.get("/export")
def export(class_id: int | None = None, event_id: int | None = None, student_id: int | None = None,
           date_from: datetime | None = None, date_to: datetime | None = None,
           grade_scale_id: int | None = None,
           format: str = Query("csv", pattern="^(csv|xlsx|pdf)$"),
           actor: User = Depends(require_permission("event.manage")), db: DbSession = Depends(get_db)) -> Response:
    data = get_analytics(db, actor, class_id=class_id, event_id=event_id, student_id=student_id,
                         date_from=date_from, date_to=date_to, grade_scale_id=grade_scale_id)
    columns = ["student_id", "display_name", "started", "completed", "attempts", "hints", "score", "grade", "last_activity"]
    export_rows = [{**row, "grade": row["grade"]["value"] if row.get("grade") else ""} for row in data["students"]]
    if format == "csv":
        stream = StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({key: _spreadsheet_safe(value) for key, value in row.items()} for row in export_rows)
        return Response("\ufeff" + stream.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=cyberlab-results.csv"})
    if format == "xlsx":
        rows = [columns] + [[str(row.get(col) or "") for col in columns] for row in export_rows]
        xml_rows = []
        for ridx, row in enumerate(rows, 1):
            cells = "".join(f'<c r="{chr(64 + cidx)}{ridx}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>' for cidx, value in enumerate(row, 1))
            xml_rows.append(f'<row r="{ridx}">{cells}</row>')
        sheet = '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(xml_rows) + "</sheetData></worksheet>"
        output = BytesIO()
        with ZipFile(output, "w", ZIP_DEFLATED) as book:
            book.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
            book.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
            book.writestr("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Resultados" sheetId="1" r:id="rId1"/></sheets></workbook>')
            book.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
            book.writestr("xl/worksheets/sheet1.xml", sheet)
        return Response(output.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=cyberlab-results.xlsx"})
    lines = ["CYBERLAB - Resultados", str(data["scope"]["name"]), "", " | ".join(columns)]
    lines.extend(" | ".join(str(row.get(col) or "") for col in columns) for row in export_rows)
    def pdf_line(line: str) -> str:
        return line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    chunks = [lines[index:index + 55] for index in range(0, len(lines), 55)] or [[]]
    streams = [("BT /F1 9 Tf 40 800 Td 12 TL " + " ".join(f"({pdf_line(line)[:150]}) Tj T*" for line in chunk) + " ET").encode("latin-1", "replace") for chunk in chunks]
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b""]
    page_ids = [4 + index * 2 for index in range(len(streams))]
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(f'{page_id} 0 R' for page_id in page_ids)}] /Count {len(page_ids)} >>".encode()
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for index, pdf_stream in enumerate(streams):
        page_id = page_ids[index]
        content_id = page_id + 1
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>".encode())
        objects.append(b"<< /Length " + str(len(pdf_stream)).encode() + b" >>\nstream\n" + pdf_stream + b"\nendstream")
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(pdf)); pdf.extend(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(pdf); pdf.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]: pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return Response(bytes(pdf), media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=cyberlab-results.pdf"})


def _spreadsheet_safe(value: object) -> object:
    """Prevent spreadsheet programs from evaluating untrusted exported text as formulas."""
    if isinstance(value, str) and value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


@router.get("/announcements")
def announcements(class_id: int | None = None, event_id: int | None = None, include_archived: bool = False,
                  actor: User = Depends(require_permission("event.manage")), db: DbSession = Depends(get_db)) -> list[dict[str, Any]]:
    rows = list_announcements(db, actor, class_id=class_id, event_id=event_id, include_archived=include_archived)
    return [{"id": row.id, "class_id": row.class_id, "event_id": row.event_id, "title": row.title,
        "content_markdown": row.content_markdown, "publish_at": row.publish_at, "archived_at": row.archived_at} for row in rows]


@router.post("/announcements", dependencies=[Depends(require_csrf)])
def create_announcement(payload: AnnouncementInput, actor: User = Depends(require_permission("event.manage")), db: DbSession = Depends(get_db)) -> dict[str, Any]:
    row = create_announcement_service(db, actor, class_id=payload.class_id, event_id=payload.event_id, title=payload.title, content_markdown=payload.content_markdown, publish_at=payload.publish_at)
    audit.log(db, "ANNOUNCEMENT_CREATED", actor.id, "announcement", meta={"class_id": payload.class_id, "event_id": payload.event_id})
    db.commit()
    db.refresh(row)
    return {"id": row.id, "title": row.title, "publish_at": row.publish_at}


@router.post("/announcements/{announcement_id}/archive", dependencies=[Depends(require_csrf)])
def archive_announcement(announcement_id: int, actor: User = Depends(require_permission("event.manage")), db: DbSession = Depends(get_db)) -> dict[str, bool]:
    row = db.get(Announcement, announcement_id)
    if row is None:
        raise HTTPException(404, "announcement not found")
    archive_announcement_service(db, actor, row)
    audit.log(db, "ANNOUNCEMENT_ARCHIVED", actor.id, "announcement", str(row.id))
    db.commit()
    return {"ok": True}


@router.post("/events/{event_id}/close", dependencies=[Depends(require_csrf)])
def close_event(event_id: int, actor: User = Depends(require_permission("event.manage")), db: DbSession = Depends(get_db)) -> dict[str, object]:
    event = close_event_service(db, actor, event_id)
    audit.log(db, "EVENT_CLOSED", actor.id, "ctf_event", str(event.id))
    db.commit()
    return {"id": event.id, "status": event.status, "ends_at": event.ends_at}
