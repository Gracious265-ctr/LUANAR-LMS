from supabase import create_client

from django.conf import settings


def get_supabase_client():
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        raise ValueError(
            "Supabase credentials are not configured. "
            "Set SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables."
        )
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


def upload_document(file, application_id: str) -> dict:
    client = get_supabase_client()
    path = f"leave-documents/{application_id}/{file.name}"
    client.storage.from_(settings.SUPABASE_BUCKET).upload(
        path, file.read(), {"content-type": file.content_type}
    )
    result = client.storage.from_(settings.SUPABASE_BUCKET).create_signed_url(
        path, settings.SUPABASE_SIGNED_URL_EXPIRY
    )
    return {"path": path, "url": result["signedURL"]}


def delete_document(file_path: str) -> None:
    client = get_supabase_client()
    client.storage.from_(settings.SUPABASE_BUCKET).remove([file_path])
