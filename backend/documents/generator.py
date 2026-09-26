"""Approved leave document PDF renderer (Unit 23).

``generate_approved_document`` renders the official approved-leave document for
an application through ReportLab, laid out exclusively from the singleton
``LeaveDocumentTemplate`` configuration (header, title, intro, the configured
ordered field rows, closing, signature areas, footer) and the approved
``LeaveApplication`` record as the data source. The function is pure: it
touches no database rows and no storage backend — the caller decides where the
bytes go (see ``documents.finalisation``).
"""

from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from leave.models import LeaveApplication, LeaveType

from .services import FIELD_CATALOG, get_template

_VALUE_KEYS = tuple(item["key"] for item in FIELD_CATALOG)


def generate_approved_document(application: LeaveApplication) -> bytes:
    """Render and return the approved leave document for ``application`` as PDF bytes."""
    template = get_template()
    values = _resolve_values(application)

    story = []
    if template.header:
        story.append(Paragraph(template.header, _header_style()))
        story.append(Spacer(1, 14))
    story.append(Paragraph(template.title, _title_style()))
    story.append(Spacer(1, 20))
    if template.intro:
        story.append(Paragraph(template.intro, _body_style()))
        story.append(Spacer(1, 14))

    if template.fields:
        rows = [
            [
                Paragraph(str(row.get("label") or ""), _label_style()),
                Paragraph(str(values.get(row.get("key"), "") or ""), _value_style()),
            ]
            for row in template.fields
            if row.get("key") in _VALUE_KEYS
        ]
        if rows:
            table = Table(rows, colWidths=[2.2 * inch, 3.8 * inch])
            table.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("GRID", (0, 0), (-1, -1), 0.5, "#9aa0a6"),
                        ("BACKGROUND", (0, 0), (0, -1), "#eef0f2"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.append(table)
            story.append(Spacer(1, 20))

    if template.closing:
        story.append(Paragraph(template.closing, _body_style()))
        story.append(Spacer(1, 28))

    for area in template.signature_areas:
        label = str((area or {}).get("label") or "")
        story.append(Paragraph(label, _signature_style()))
        story.append(Spacer(1, 36))

    story.append(Spacer(1, 28))
    if template.footer:
        story.append(Paragraph(template.footer, _footer_style()))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=inch,
        rightMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
        title=str(template.title),
        author="LUANAR Leave Management System",
    )
    doc.build(story)
    return buffer.getvalue()


def _resolve_values(application: LeaveApplication) -> dict:
    """Project the approved application onto the fixed field-catalog keys."""
    profile = getattr(application.employee, "employee_profile", None)
    return {
        "reference": application.reference_number or "",
        "employee_name": (
            application.employee.get_full_name() or application.employee.username
            or ""
        ),
        "employee_grade": (profile.grade if profile else "") or "",
        "designation": (profile.designation if profile else "") or "",
        "department": (profile.department if profile else "") or "",
        "leave_type": _leave_type_name(application),
        "start_date": _iso(application.start_date),
        "end_date": _iso(application.end_date),
        "working_days": (
            str(application.working_days) if application.working_days else ""
        ),
        "request_reason": application.reason or "",
    }


def _leave_type_name(application: LeaveApplication) -> str:
    if application.leave_type_id is None:
        return ""
    name = (
        LeaveType.objects.filter(pk=application.leave_type_id)
        .values_list("name", flat=True)
        .first()
    )
    if name:
        return name
    snapshot = application.rules_snapshot or {}
    return (snapshot.get("leave_type") or {}).get("name") or ""


def _iso(value) -> str:
    return value.isoformat() if value else ""


def _paragraph(text: str, style) -> Paragraph:
    return Paragraph(text, style)


def _header_style() -> ParagraphStyle:
    return ParagraphStyle(
        name="ApprovedHeader",
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        alignment=1,
        spaceAfter=6,
    )


def _title_style() -> ParagraphStyle:
    return ParagraphStyle(
        name="ApprovedTitle",
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        alignment=1,
    )


def _body_style() -> ParagraphStyle:
    return ParagraphStyle(
        name="ApprovedBody",
        fontName="Helvetica",
        fontSize=11,
        leading=15,
        alignment=4,
    )


def _label_style() -> ParagraphStyle:
    return ParagraphStyle(
        name="ApprovedLabel",
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
    )


def _value_style() -> ParagraphStyle:
    return ParagraphStyle(
        name="ApprovedValue",
        fontName="Helvetica",
        fontSize=10.5,
        leading=14,
    )


def _signature_style() -> ParagraphStyle:
    return ParagraphStyle(
        name="ApprovedSignature",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
    )


def _footer_style() -> ParagraphStyle:
    return ParagraphStyle(
        name="ApprovedFooter",
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        alignment=1,
        textColor="#5f6368",
    )