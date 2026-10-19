"""Official leave-document template configuration and approved-document rendering.

The template half is HR-owned configuration (Unit 10). The rendering half
(Unit 23b) turns an approved application plus that configuration into the
official PDF, using ReportLab.
"""

import logging
from io import BytesIO
from xml.sax.saxutils import escape

from django.db import transaction

from .models import ApprovedLeaveDocument, LeaveDocumentTemplate

logger = logging.getLogger(__name__)

DEFAULT_TITLE = "APPROVED LEAVE"
DEFAULT_HEADER = "LILONGWE UNIVERSITY OF AGRICULTURE AND NATURAL RESOURCES"
DEFAULT_INTRO = (
    "This is to certify that the under-listed employee has been granted the "
    "following leave in accordance with the university leave regulations:"
)
DEFAULT_CLOSING = (
    "The approved leave is granted subject to the university leave regulations."
)
DEFAULT_FOOTER = "LUANAR"

# The single source of truth for the document's fixed data fields. ``sample``
# is presentational example data for the HR preview only; the authoritative
# rendering for real applications reads the approved application record
# (Unit 23b). The API exposes this catalog so the frontend does not duplicate it.
FIELD_CATALOG: list[dict] = [
    {"key": "reference", "label": "Reference", "sample": "LV-2026-000123"},
    {"key": "employee_name", "label": "Employee", "sample": "Jane Employee"},
    {"key": "employee_grade", "label": "Grade", "sample": "G"},
    {"key": "designation", "label": "Designation", "sample": "Lecturer"},
    {"key": "team", "label": "Team", "sample": "Agronomy Team"},
    {"key": "leave_type", "label": "Leave type", "sample": "Annual leave"},
    {"key": "start_date", "label": "Start date", "sample": "2026-10-05"},
    {"key": "end_date", "label": "End date", "sample": "2026-10-23"},
    {"key": "working_days", "label": "Working days", "sample": "15"},
    {"key": "request_reason", "label": "Reason", "sample": "Personal leave"},
    # Added by Unit 23b — purely additive, so every existing template row stays
    # valid. ``remaining_balance`` is read from the ledger-backed balance
    # provider at render time, after the approval transaction has committed the
    # deduction, so it reflects the deduction.
    {
        "key": "approved_on",
        "label": "Approved on",
        "sample": "2026-09-25",
    },
    {
        "key": "remaining_balance",
        "label": "Remaining balance (days)",
        "sample": "9",
    },
]

ALLOWED_FIELD_KEYS: tuple[str, ...] = tuple(item["key"] for item in FIELD_CATALOG)

DEFAULT_FIELDS: list[dict] = [
    {"key": item["key"], "label": item["label"]} for item in FIELD_CATALOG
]

DEFAULT_SIGNATURE_AREAS: list[dict] = [
    {"label": "Employee signature"},
    {"label": "For: Registrar"},
]

MAX_SIGNATURE_AREAS = 8
MAX_TEXT_LENGTH = 2000


def get_template() -> LeaveDocumentTemplate:
    """Return the single official template, creating the default on first use.

    There is exactly one leave-document template (a singleton). No template row
    exists until the first access materializes the editable default, so API
    reads never 404 and new clones need no seed data. Values are never edited
    here; the configuration (wording, labels, order, signature areas) is.
    """
    template, created = LeaveDocumentTemplate.objects.get_or_create(
        pk=1,
        defaults={
            "title": DEFAULT_TITLE,
            "header": DEFAULT_HEADER,
            "intro": DEFAULT_INTRO,
            "fields": DEFAULT_FIELDS,
            "closing": DEFAULT_CLOSING,
            "signature_areas": DEFAULT_SIGNATURE_AREAS,
            "footer": DEFAULT_FOOTER,
        },
    )
    return template


# ---------------------------------------------------------------------------
# Approved-document rendering (Unit 23b)
# ---------------------------------------------------------------------------

#: The generated file's name stem and content type.
APPROVED_DOCUMENT_FILENAME = "approved-leave.pdf"
APPROVED_DOCUMENT_CONTENT_TYPE = "application/pdf"


def _text(value) -> str:
    """Render any catalog value as trimmed display text; missing becomes blank."""
    if value is None:
        return ""
    return str(value).strip()


def document_values(application) -> dict[str, str]:
    """The single mapping every catalog key resolves through (D4, D11).

    Values come only from the persisted approved application and the employee's
    HR record — never from a catalog ``sample``, which exists for the HR preview
    alone. A key that cannot be resolved maps to ``""`` so a template HR has
    edited can never break the render task.
    """
    from django.utils import timezone

    from leave.providers import get_provider
    from leave_config.models import LeaveType

    employee = application.employee
    profile = getattr(employee, "employee_profile", None)
    leave_type = (
        LeaveType.objects.filter(pk=application.leave_type_id)
        .values_list("name", flat=True)
        .first()
    )

    remaining_balance = ""
    if application.financial_year_label:
        remaining_balance = get_provider().get_available_balance(
            employee.id, application.financial_year_label
        )

    approved_on = application.approved_on
    return {
        "reference": _text(application.reference_number),
        "employee_name": _text(employee.get_full_name()),
        "employee_grade": _text(getattr(profile, "grade", "")),
        "designation": _text(getattr(profile, "designation", "")),
        "team": _text(getattr(getattr(profile, "team", None), "name", "")),
        "leave_type": _text(leave_type),
        "start_date": _text(application.start_date),
        "end_date": _text(application.end_date),
        "working_days": _text(application.working_days),
        "request_reason": _text(application.reason),
        "approved_on": _text(
            timezone.localtime(approved_on).date().isoformat() if approved_on else ""
        ),
        "remaining_balance": _text(remaining_balance),
    }


def render_approved_document_pdf(application) -> bytes:
    """Render the official approved-leave PDF for ``application`` (D11).

    Walks the configured template in order and resolves each field key through
    :func:`document_values`. An unknown key or an unresolved value renders blank
    rather than raising, so HR's editable template can never break a render.
    """
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    template = get_template()
    values = document_values(application)

    buffer = BytesIO()
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=template.title or DEFAULT_TITLE,
        author=DEFAULT_FOOTER,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle", parent=styles["Title"], fontSize=16, leading=20, spaceAfter=4 * mm
    )
    centered = ParagraphStyle("DocCentered", parent=styles["Normal"], alignment=TA_CENTER)
    label_style = ParagraphStyle("DocLabel", parent=styles["Normal"], fontSize=9)
    value_style = ParagraphStyle("DocValue", parent=styles["Normal"], fontSize=10)

    story: list = []
    if template.header:
        story.append(Paragraph(escape(template.header), centered))
        story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(escape(template.title or DEFAULT_TITLE), title_style))
    if template.intro:
        story.append(Paragraph(escape(template.intro), styles["Normal"]))
        story.append(Spacer(1, 5 * mm))

    rows = [
        [
            Paragraph(escape(str(field.get("label") or field.get("key") or "")), label_style),
            Paragraph(escape(values.get(str(field.get("key", "")), "")), value_style),
        ]
        for field in (template.fields or [])
    ]
    if rows:
        table = Table(rows, colWidths=[55 * mm, 105 * mm], hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#dddddd")),
                ]
            )
        )
        story.append(table)

    if template.closing:
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph(escape(template.closing), styles["Normal"]))

    captions = [
        str(area.get("label", "")).strip()
        for area in (template.signature_areas or [])[:MAX_SIGNATURE_AREAS]
        if str(area.get("label", "")).strip()
    ]
    if captions:
        story.append(Spacer(1, 18 * mm))
        width = 160 * mm / len(captions)
        signature_table = Table(
            [[Paragraph(escape(caption), label_style) for caption in captions]],
            colWidths=[width] * len(captions),
        )
        signature_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("LINEABOVE", (0, 0), (-1, -1), 0.5, colors.black),
                ]
            )
        )
        story.append(signature_table)

    if template.footer:
        story.append(Spacer(1, 10 * mm))
        story.append(Paragraph(escape(template.footer), centered))

    pdf.build(story)
    return buffer.getvalue()


def approved_document_payload(document) -> dict:
    """The document's public shape, with a signed URL only when one exists.

    A ``pending`` or ``failed`` row reports its status and ``available: False``
    so the client can say "being prepared" from the first response rather than
    needing a second request to discover there is nothing to open.

    Minting the signed URL is enrichment on top of the document row, not the row
    itself, so a storage problem degrades the payload instead of failing the
    request. ``available`` is an explicit promise that ``download_url`` opens
    *now*; when a fresh URL cannot be minted the promise is withdrawn rather than
    served from the render-time URL, which by then has expired and would hand the
    employee a dead link. The other storage call sites fall back to that stored
    URL because they are best-effort listings, but this payload is the one the UI
    keys an "Open" button off, so no button is honest and a broken link is not.
    """
    from leave.services.storage import signed_document_url

    available = document.status == ApprovedLeaveDocument.Status.READY
    payload = {
        "id": str(document.pk),
        "application": str(document.application_id),
        "status": document.status,
        "available": available,
        "file_name": document.file_name or "",
        "content_type": document.content_type or "",
        "file_size": document.file_size or 0,
        "approved_on": document.approved_on,
        "rendered_at": document.rendered_at,
        "created_at": document.created_at,
        "download_url": "",
    }
    if available and document.file_path:
        # Signed URLs expire, so re-sign from the stored path rather than handing
        # back the URL captured at render time.
        try:
            payload["download_url"] = signed_document_url(document.file_path)
        except Exception:
            logger.exception(
                "Could not sign a download URL for approved document %s; "
                "reporting it as unavailable rather than failing the request.",
                document.pk,
            )
            payload["available"] = False
    return payload


def enqueue_approved_document_render(document) -> None:
    """Queue the render for ``document`` once the approval commits (D5).

    The document is a retryable derived artifact, so a broker that is not
    reachable is logged and swallowed: the approval has already committed and
    must not be undone by a missing worker. The row stays ``pending``.
    """
    from django_q.tasks import async_task

    document_id = document.pk

    def _dispatch() -> None:
        try:
            async_task("documents.tasks.render_approved_document", document_id)
        except Exception:
            logger.exception(
                "Could not enqueue the approved-document render for %s", document_id
            )

    transaction.on_commit(_dispatch)
