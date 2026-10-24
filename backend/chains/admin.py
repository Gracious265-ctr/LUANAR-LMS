from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet

from roles.models import ApproverRole

from .models import Section, SectionMember, Workflow


class SectionForm(forms.ModelForm):
    """Inline form for one workflow section.

    ``approver_role`` is chosen by ``code`` rather than by primary key, matching
    the workflow API: a saved workflow reads "hod", and HR picks a role by what it
    is called instead of by an id they have no way to look up.
    """

    approver_role = forms.ModelChoiceField(
        queryset=ApproverRole.objects.all(),
        to_field_name="code",
        label="Approver role",
    )

    class Meta:
        model = Section
        fields = "__all__"

    def clean_order(self):
        order = self.cleaned_data.get("order")
        if order is not None and order < 1:
            raise ValidationError("Section order must be 1 or greater.")
        return order

    def clean_approver_role(self):
        role = self.cleaned_data.get("approver_role")
        if role is not None and not role.is_active:
            raise ValidationError(
                f'"{role.label}" is deactivated. Reactivate it in Roles, or '
                "pick an active role."
            )
        return role


class SectionInlineFormSet(BaseInlineFormSet):
    """Rejects a workflow whose sections do not have distinct positions.

    ``Section``'s unique constraint on ``(workflow, order)`` would catch this
    too, but as a database error at save time. Validating in the formset names
    the problem where HR can act on it, and does so for the whole form rather
    than failing on whichever row happened to be written first.

    A repeated approver role is deliberately *not* re-checked here (Unit 30). It
    needs no second implementation: ``section_workflow_role_unique`` is a model
    constraint, so Django's own cross-form ``validate_unique`` already reports the
    repeat on the ``approver_role`` field, where HR can act on it. Letting the
    model constraint answer is also what keeps the admin and the API agreeing by
    construction rather than by two code paths kept in step by hand.
    """

    def clean(self):
        super().clean()
        orders = [
            form.cleaned_data.get("order")
            for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get("DELETE")
        ]
        duplicates = {o for o in orders if o is not None and orders.count(o) > 1}
        if duplicates:
            raise ValidationError(
                "Each approval section needs its own position. These numbers are "
                f"used more than once: {', '.join(str(o) for o in sorted(duplicates))}."
            )


class SectionInline(admin.TabularInline):
    """Workflow sections, in approval order.

    A repeated approver role is refused: since Unit 30 a role belongs to exactly
    one stage of a workflow, so that one office cannot sign off twice at two
    points in the same chain. The same role may still be used by a different
    workflow.
    """

    model = Section
    form = SectionForm
    formset = SectionInlineFormSet
    extra = 1
    min_num = 1
    validate_min = True
    ordering = ("order",)


class WorkflowAdminForm(forms.ModelForm):
    """Kept for the section inline; the chain itself is not editable here.

    A chain is created and rewritten with its team, so this form only ever
    renders for the read-only inspector's inlines, which do not validate a
    lifecycle of their own.
    """

    class Meta:
        model = Workflow
        fields = "__all__"


@admin.register(Workflow)
class WorkflowAdmin(admin.ModelAdmin):
    """Read-only inspector. A chain is written through its team.

    A chain is created with its team and its steps are rewritten by saving the
    team again, so this page exists to answer "what is this team's chain, and
    when did it last change" — not to be a second place to edit it. Leaving the
    write open here would let a chain be edited apart from the team whose
    applications it governs, which is precisely the mistake the team-owned
    chain rules out everywhere else.
    """

    form = WorkflowAdminForm
    list_display = (
        "name",
        "owner",
        "effective_from",
        "is_active",
        "section_summary",
    )
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("name",)
    inlines = [SectionInline]

    def get_queryset(self, request):
        # ``stages__approver_role`` as well: the summary renders role labels, so
        # without it the list page runs one query per stage.
        return super().get_queryset(request).prefetch_related(
            "sections__approver_role"
        )

    def section_summary(self, obj):
        # ``approver_role`` is a related row now, so show its label rather than
        # the default ``__str__`` — the summary reads "Supervisor → HOD → …".
        labels = [section.approver_role.label for section in obj.sections.all()]
        return " \u2192 ".join(labels) if labels else "—"

    section_summary.short_description = "Approval sections"

    @admin.display(description="Team")
    def owner(self, obj):
        team = getattr(obj, "team", None)
        return team.name if team else "—"

    def has_add_permission(self, request):
        # A chain without a team is a chain nothing routes through.
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # PROTECTed by Team.workflow, and the audit trail is the record of why
        # a chain looked the way it did.
        return False


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("name", "workflow", "order", "approver_role", "member_count", "is_active")
    list_filter = ("is_active", "workflow", "approver_role")
    search_fields = ("name", "workflow__name")
    raw_id_fields = ("workflow",)
    ordering = ("workflow__name", "order")

    @admin.display(description="Members")
    def member_count(self, obj):
        return obj.members.count()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SectionMember)
class SectionMemberAdmin(admin.ModelAdmin):
    list_display = ("section", "user", "created_at")
    list_filter = ("section__workflow",)
    search_fields = (
        "section__name",
        "user__first_name",
        "user__last_name",
        "user__email",
    )
    raw_id_fields = ("section", "user")
