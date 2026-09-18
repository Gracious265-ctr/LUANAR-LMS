"""Official leave-document template configuration logic for the documents app."""

from .models import LeaveDocumentTemplate

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
# rendering for real applications (Unit 23) reads the approved application
# record. The API exposes this catalog so the frontend does not duplicate it.
FIELD_CATALOG: list[dict] = [
    {"key": "reference", "label": "Reference", "sample": "LV-2026-000123"},
    {"key": "employee_name", "label": "Employee", "sample": "Jane Employee"},
    {"key": "employee_grade", "label": "Grade", "sample": "G"},
    {"key": "designation", "label": "Designation", "sample": "Lecturer"},
    {
        "key": "department",
        "label": "Department",
        "sample": "Department of Agronomy",
    },
    {"key": "leave_type", "label": "Leave type", "sample": "Annual leave"},
    {"key": "start_date", "label": "Start date", "sample": "2026-10-05"},
    {"key": "end_date", "label": "End date", "sample": "2026-10-23"},
    {"key": "working_days", "label": "Working days", "sample": "15"},
    {"key": "request_reason", "label": "Reason", "sample": "Personal leave"},
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