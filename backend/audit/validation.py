"""Shared query-param validation for list filters.

Typed ORM lookups (``IntegerField``/``UUIDField``/``date__year``) raise
``ValueError``/``ValidationError`` which DRF's exception handler does not
translate, surfacing as 500s. These helpers coerce first and raise a clear
400 instead.
"""

from typing import Any
from uuid import UUID

from rest_framework.exceptions import ValidationError


def positive_int(value: Any, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValidationError({field: "Must be a positive integer."})
    if parsed < 0:
        raise ValidationError({field: "Must be a positive integer."})
    return parsed


def uuid_value(value: Any, field: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        raise ValidationError({field: "Must be a valid UUID."})