"""Local-filesystem document storage backend (Unit 19).

Writes uploaded supporting documents under ``settings.LEAVE_STORAGE_ROOT`` so
uploads/downloads work without any external credentials. Path traversal (``..``
segments and absolute paths) is rejected by ``_safe_path``.
"""

import os
from pathlib import Path

from django.conf import settings


class DevelopmentStorageBackend:
    """Store document bytes as plain files under ``LEAVE_STORAGE_ROOT``."""

    def __init__(self):
        self.root = Path(settings.LEAVE_STORAGE_ROOT)

    def _safe_path(self, path: str) -> Path:
        if not path or path.startswith("/") or os.path.isabs(path):
            raise ValueError("Invalid storage path.")
        raw = Path(path)
        if ".." in raw.parts:
            raise ValueError("Invalid storage path.")
        return self.root.joinpath(*raw.parts)

    def put(self, *, path: str, file_obj, content_type: str) -> None:
        target = self._safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = file_obj if isinstance(file_obj, bytes) else file_obj.read()
        target.write_bytes(data)

    def remove(self, path: str) -> None:
        target = self._safe_path(path)
        if target.exists():
            target.unlink()

    def exists(self, path: str) -> bool:
        return self._safe_path(path).is_file()

    def open(self, path: str):
        return self._safe_path(path).open("rb")

    def signed_url(self, path: str, *, expires: int = 60) -> str:
        """Dev backend has no auth/signing; treat as unsupported (→ 503)."""
        raise ValueError(
            "Signed URLs are not supported by the local storage backend."
        )