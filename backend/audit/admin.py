from django.contrib import admin
from django.db import models

<<<<<<< HEAD
from .models import AuditEvent
from .services import record_config_change
=======
from .models import AuditEntry
>>>>>>> feature/plans-teams


@admin.register(AuditEntry)
class AuditEntryAdmin(admin.ModelAdmin):
    """View-only inspector for the append-only audit log."""

    list_display = (
        "actor",
        "action",
        "target_type",
        "target_id",
        "target_summary",
        "created_at",
    )
    list_filter = ("action", "target_type")
    search_fields = (
        "actor__first_name",
        "actor__last_name",
        "actor__email",
        "target_summary",
        "target_id",
    )
    raw_id_fields = ("actor",)
    readonly_fields = (
        "actor",
        "action",
        "target_type",
        "target_id",
        "target_summary",
        "detail",
        "reason",
        "created_at",
    )
    ordering = ("-created_at",)

    def has_delete_permission(self, request, obj=None):
<<<<<<< HEAD
        return False

    def has_change_permission(self, request, obj=None):
        return False


class AuditedModelAdmin(admin.ModelAdmin):
    """Admin that records HR-config edits to the audit trail.

    Mix into a configuration :class:`ModelAdmin` (structure, rules,
    entitlements, workflows, ...) so an edit made through the Django admin
    writes the same :func:`record_config_change` rows the API serializers do.
    The action code is ``<app_label>.<model>.created|updated|deleted`` and the
    actor is the logged-in admin user. Foreign keys and content-type relations
    are snapshotted by primary key so the metadata stays JSON-serializable.
    """

    audit_ignore_fields: frozenset[str] = frozenset()

    def _audit_snapshot(self, obj) -> dict:
        snapshot: dict = {}
        for field in obj._meta.concrete_fields:
            if field.name in self.audit_ignore_fields:
                continue
            value = getattr(obj, field.name)
            if isinstance(value, models.Model):
                value = value.pk
            snapshot[field.name] = value
        return snapshot

    def _snapshot_from_db(self, obj) -> dict | None:
        """The persisted snapshot before the form mutates the in-memory row."""
        if obj.pk is None:
            return None
        try:
            return self._audit_snapshot(self.model.objects.get(pk=obj.pk))
        except self.model.DoesNotExist:
            return None

    def _record_admin_audit(self, request, obj, *, action: str, before=None) -> None:
        user = getattr(request, "user", None)
        if user is None:
            return
        record_config_change(
            actor=user,
            action=f"{obj._meta.app_label}.{obj._meta.model_name}.{action}",
            target=obj,
            before=before,
            after=self._audit_snapshot(obj) if action != "deleted" else None,
        )

    def save_model(self, request, obj, form, change):
        before = self._snapshot_from_db(obj) if change else None
        super().save_model(request, obj, form, change)
        self._record_admin_audit(
            request, obj, action="updated" if change else "created", before=before
        )

    def delete_model(self, request, obj):
        self._record_admin_audit(
            request, obj, action="deleted", before=self._audit_snapshot(obj)
        )
        super().delete_model(request, obj)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for obj in formset.deleted_objects:
            self._record_admin_audit(
                request, obj, action="deleted", before=self._audit_snapshot(obj)
            )
            obj.delete()
        for obj in instances:
            is_new = obj.pk is None
            before = None if is_new else self._snapshot_from_db(obj)
            obj.save()
            self._record_admin_audit(
                request, obj, action="created" if is_new else "updated", before=before
            )
        formset.save_m2m()
=======
        return False
>>>>>>> feature/plans-teams
