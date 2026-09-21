import unicodedata
from pathlib import PurePosixPath
from uuid import uuid4

from supabase import create_client

from django.conf import settings

MAX_DOCUMENT_SIZE = 10 * 1024 * 1024

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
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


def upload_document(file, application_id: str) -> dict:
    client = get_supabase_client()
    safe_name = _sanitize_document_name(file.name)
    path = f"leave-documents/{application_id}/{uuid4().hex}-{safe_name}"
    client.storage.from_(settings.SUPABASE_BUCKET).upload(
        path, file.read(), {"content-type": file.content_type}
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
    """
    client = get_supabase_client()
    result = client.storage.from_(settings.SUPABASE_BUCKET).create_signed_url(
        file_path, settings.SUPABASE_SIGNED_URL_EXPIRY
    )
    return result["signedURL"]


def delete_document(file_path: str) -> None:
    client = get_supabase_client()
    client.storage.from_(settings.SUPABASE_BUCKET).remove([file_path])
