"""Storage-backend protocol (Unit 19).

Every supporting-document storage operation goes through this interface so the
document logic never depends on a specific backend (development filesystem vs
Supabase today; any future backend behind the same ``LEAVE_STORAGE_BACKEND``
setting).
"""

from typing import BinaryIO, Protocol


class StorageBackend(Protocol):
    """The minimal contract a document storage backend must satisfy."""

    def put(self, *, path: str, file_obj, content_type: str) -> None: ...

    def remove(self, path: str) -> None: ...

    def exists(self, path: str) -> bool: ...

    def open(self, path: str) -> BinaryIO: ...

    def signed_url(self, path: str, *, expires: int = 60) -> str: ...