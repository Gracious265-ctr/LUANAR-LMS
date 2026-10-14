import unicodedata
from pathlib import PurePosixPath
from uuid import uuid4

from httpx import HTTPStatusError
from supabase import create_client
from storage3.exceptions import StorageApiError

from django.conf import settings

MAX_DOCUMENT_SIZE = 10 * 1024 * 1024

#: Storage prefixes. Employee-uploaded supporting documents keep their original
#: location; the generated approved document lives under its own prefix so the
#: two artifact families never interleave (Unit 23b D6).
SUPPORTING_DOCUMENT_PREFIX = "leave-documents/"
APPROVED_DOCUMENT_PREFIX = "approved/"

ALLOWED_DOCUMENT_CONTENT_TYPES = (
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/jpeg",
    "image/png",
    "image/webp",
    "text/plain",
)


def is_allowed_document_content_type(content_type: str) -> bool:
    return (
        content_type in ALLOWED_DOCUMENT_CONTENT_TYPES
        or content_type.startswith("image/")
    )


def _sanitize_document_name(name: str) -> str:
    """A storage-safe base name: final path segment, printable chars only."""
    base = PurePosixPath((name or "").replace("\\", "/")).name
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in base)
    return cleaned.strip("._") or "document"


def get_supabase_client():
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        raise ValueError(
            "Supabase credentials are not configured. "
            "Set SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables."
        )
    url = settings.SUPABASE_URL.rstrip("/")
    if "/" in url.removeprefix("https://").removeprefix("http://"):
        raise ValueError(
            f"SUPABASE_URL must be the bare project URL "
            f"(https://<project-ref>.supabase.co), but it is "
            f"{settings.SUPABASE_URL!r}. The dashboard's 'Project URL' field "
            f"ends in /rest/v1/; copy the API URL's host only. supabase-py "
            f"appends its own service paths, so a suffixed URL sends Storage "
            f"requests to PostgREST and fails with an opaque 404."
        )
    return create_client(url, settings.SUPABASE_SERVICE_KEY)


def ping_storage() -> None:
    """A lightweight reachability check for the configured storage bucket.

    Raises when Supabase is unconfigured or the bucket cannot be listed, so the
    system-admin health panel reports storage as ``down`` rather than silently
    assuming it is up.
    """
    client = get_supabase_client()
    client.storage.from_(settings.SUPABASE_BUCKET).list()


def upload_document(
    file, application_id: str, *, prefix: str = SUPPORTING_DOCUMENT_PREFIX
) -> dict:
    client = get_supabase_client()
    safe_name = _sanitize_document_name(file.name)
    path = f"{prefix}{application_id}/{uuid4().hex}-{safe_name}"
    client.storage.from_(settings.SUPABASE_BUCKET).upload(
        path, file.read(), {"content-type": file.content_type}
    )
    result = client.storage.from_(settings.SUPABASE_BUCKET).create_signed_url(
        path, settings.SUPABASE_SIGNED_URL_EXPIRY
    )
    return {"path": path, "url": result["signedURL"]}


def upload_bytes(
    data: bytes,
    file_name: str,
    *,
    prefix: str,
    application_id: str,
    content_type: str = "application/pdf",
) -> dict:
    """Upload in-memory bytes under ``prefix`` and return ``{path, url}``.

    The generated approved document is rendered to memory rather than through an
    upload form, so it needs a bytes-friendly sibling of :func:`upload_document`
    (Unit 23b D6). Path construction is shared, so both writers land under the
    same ``{prefix}{application_id}/`` shape.
    """
    client = get_supabase_client()
    safe_name = _sanitize_document_name(file_name)
    path = f"{prefix}{application_id}/{uuid4().hex}-{safe_name}"
    client.storage.from_(settings.SUPABASE_BUCKET).upload(
        path, data, {"content-type": content_type}
    )
    result = client.storage.from_(settings.SUPABASE_BUCKET).create_signed_url(
        path, settings.SUPABASE_SIGNED_URL_EXPIRY
    )
    return {"path": path, "url": result["signedURL"]}


def signed_document_url(file_path: str) -> str:
    """A freshly generated signed URL for a stored document path.

    Signed URLs expire after ``SUPABASE_SIGNED_URL_EXPIRY`` seconds, so reads
    re-sign from the stored ``file_path`` rather than trusting a stale URL
    persisted at upload time.

    A path the bucket cannot sign raises :class:`ValueError`, the same signal an
    unconfigured client raises, because every caller already treats the two
    identically: fall back to the URL stored on the row. A row can outlive its
    object — a seeded row, an object removed out of band — and one such row must
    not fail the listing that contains it. Only "no such object" (400/404) is
    translated: a rejected key (401/403) or a broken bucket (5xx) is a real
    misconfiguration and still raises.
    """
    client = get_supabase_client()
    try:
        result = client.storage.from_(settings.SUPABASE_BUCKET).create_signed_url(
            file_path, settings.SUPABASE_SIGNED_URL_EXPIRY
        )
    except (StorageApiError, HTTPStatusError) as exc:
        status = getattr(exc, "status", None)
        if status is None:
            status = getattr(getattr(exc, "response", None), "status_code", None)
        if str(status) in {"400", "404"} or getattr(exc, "code", None) == "not_found":
            raise ValueError(
                f"Stored document {file_path!r} is not in the storage bucket."
            ) from exc
        raise
    return result["signedURL"]


def safe_signed_document_url(file_path: str, fallback: str = "") -> str:
    """Best-effort re-sign for list/detail listings.

    Storage failures — an unconfigured client (``ValueError``), a missing
    object (``StorageApiError`` 404), or a network error — must degrade the
    payload instead of failing the whole request, so this falls back to the
    stored URL. The approved-document and approver-download views deliberately
    keep the exception: there a fresh URL is a promise that must be withdrawn
    rather than replaced by an expired one.
    """
    try:
        return signed_document_url(file_path)
    except Exception:
        return fallback


def delete_document(file_path: str) -> None:
    client = get_supabase_client()
    client.storage.from_(settings.SUPABASE_BUCKET).remove([file_path])
