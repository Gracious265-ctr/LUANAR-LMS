from rest_framework import serializers

from .models import LeaveDocumentTemplate
from .services import (
    ALLOWED_FIELD_KEYS,
    FIELD_CATALOG,
    MAX_SIGNATURE_AREAS,
    MAX_TEXT_LENGTH,
)


class LeaveDocumentTemplateSerializer(serializers.ModelSerializer):
    """HR-facing serializer for the single official leave-document template.

    HR controls presentation (wording, labels, inclusion/order of the fixed
    field catalog, signature captions). Values are never accepted — approved
    application data is out of scope by design. ``available_fields`` exposes
    the backend-owned catalog (key, default label, preview sample) so the
    frontend never hardcodes it.
    """

    available_fields = serializers.SerializerMethodField()

    class Meta:
        model = LeaveDocumentTemplate
        fields = [
            "title",
            "header",
            "intro",
            "fields",
            "closing",
            "signature_areas",
            "footer",
            "available_fields",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]

    def get_available_fields(self, obj) -> list[dict]:
        return FIELD_CATALOG

    def validate_title(self, value: str) -> str:
        title = (value or "").strip()
        if not title:
            raise serializers.ValidationError("A document title is required.")
        return title

    def validate_header(self, value: str) -> str:
        return self._bounded_text(value, "header")

    def validate_intro(self, value: str) -> str:
        return self._bounded_text(value, "intro")

    def validate_closing(self, value: str) -> str:
        return self._bounded_text(value, "closing")

    def validate_footer(self, value: str) -> str:
        return self._bounded_text(value, "footer")

    def _bounded_text(self, value: object, field: str) -> str:
        text = (value or "").strip()
        if len(text) > MAX_TEXT_LENGTH:
            raise serializers.ValidationError(
                f"{field.capitalize()} must be at most {MAX_TEXT_LENGTH} characters."
            )
        return text

    def validate_fields(self, value: list) -> list:
        validated: list[dict] = []
        seen_keys: set[str] = set()
        for index, row in enumerate(value):
            self._validate_field_row(row, index, validated, seen_keys)
        return validated

    def _validate_field_row(
        self,
        row: object,
        index: int,
        validated: list[dict],
        seen_keys: set[str],
    ) -> None:
        if not isinstance(row, dict):
            raise serializers.ValidationError(
                f"Field {index + 1} must be an object with key and label."
            )
        key = row.get("key")
        if key not in ALLOWED_FIELD_KEYS:
            raise serializers.ValidationError(
                f"Field {index + 1} uses an unknown data field: {key!r}."
            )
        if key in seen_keys:
            raise serializers.ValidationError(
                f"Field {index + 1} repeats the {key!r} data field."
            )
        label = (row.get("label") or "").strip()
        if not label:
            raise serializers.ValidationError(
                f"Field {index + 1} needs a non-blank label."
            )
        seen_keys.add(key)
        validated.append({"key": key, "label": label})

    def validate_signature_areas(self, value: list) -> list:
        validated: list[dict] = []
        for index, row in enumerate(value):
            if not isinstance(row, dict):
                raise serializers.ValidationError(
                    f"Signature area {index + 1} must be an object with a label."
                )
            label = (row.get("label") or "").strip()
            if not label:
                raise serializers.ValidationError(
                    f"Signature area {index + 1} needs a non-blank label."
                )
            validated.append({"label": label})
        return validated

    def validate(self, attrs: dict) -> dict:
        if "fields" in attrs and not attrs["fields"]:
            raise serializers.ValidationError(
                {"fields": "At least one data field is required."}
            )

        if (
            "signature_areas" in attrs
            and len(attrs["signature_areas"]) > MAX_SIGNATURE_AREAS
        ):
            raise serializers.ValidationError(
                {
                    "signature_areas": (
                        f"At most {MAX_SIGNATURE_AREAS} signature areas are allowed."
                    )
                }
            )
        return attrs