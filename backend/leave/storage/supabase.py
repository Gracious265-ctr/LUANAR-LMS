"""Supabase document storage backend (Unit 19).

Wraps the existing ``services/storage.py`` SDK calls behind the storage
interface: ``upload``/``remove``/``download``/``list`` on the configured bucket,
plus ``signed_url`` for the Unit 16 approver download endpoint (relocated from
``get_signed_download_url``). Fails loudly with the "credentials not configured"
error when the env vars are missing.
"""

from io import BytesIO

from supabase import create_client

from django.conf import settings


class SupabaseStorageBackend:
    """Store document bytes in the configured Supabase storage bucket."""

    def __init__(self):
        self.client = None

    def _client(self):
        if self.client is not None:
            return self.client
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
            raise ValueError(
                "Supabase credentials are not configured. "
                "Set SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables."
            )
        self.client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        return self.client

    def _bucket(self):
        return self._client().storage.from_(settings.SUPABASE_BUCKET)

    def put(self, *, path: str, file_obj, content_type: str) -> None:
        data = file_obj if isinstance(file_obj, bytes) else file_obj.read()
        self._bucket().upload(path, data, {"content-type": content_type})

    def remove(self, path: str) -> None:
        self._bucket().remove([path])

    def exists(self, path: str) -> bool:
        folder, _, name = path.rpartition("/")
        try:
            items = self._bucket().list(folder, {"search": name, "limit": 1})
        except Exception:
            return False
        return any(item.get("name") == name for item in items)

    def open(self, path: str):
        data = self._bucket().download(path)
        return BytesIO(data)

    def signed_url(self, path: str, expires: int | None = None) -> str:
        """Return a short-lived signed download URL for ``path``.

        Falls back to ``SUPABASE_SIGNED_URL_EXPIRY`` when no explicit expiry is
        given. Mirrors the former ``get_signed_download_url`` helper so the
        Unit 16 approver download endpoint keeps its behaviour.
        """
        result = self._bucket().create_signed_url(
            path, expires or settings.SUPABASE_SIGNED_URL_EXPIRY
        )
        return result["signedURL"]