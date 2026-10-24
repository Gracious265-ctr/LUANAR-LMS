"""Workflow, team, and section-membership HTTP API."""

from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError
from rest_framework import mixins, permissions, response, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import viewsets
from rest_framework import serializers as drf_serializers

from audit.validation import positive_int
from users.models import EmployeeProfile, User

from campuses.models import Campus, CampusRoleAssignment
from roles.models import ApproverRole, RoleAssignment
from roles.permissions import IsHROnly, IsHROrTeamManager
from roles.serializers import ApproverRoleSerializer
from roles.services import (
    RoleActionError,
    WorkflowMemberError,
    wide_approver_ids_for_team,
)
from teams.models import Team, TeamRoleAssignment
from users.serializers import EmployeeSerializer
from chains.models import Section, SectionMember, Workflow, WorkflowMember

from .serializers import SectionMemberSerializer, SectionMemberWriteSerializer, TeamMemberAddSerializer, TeamMemberSummarySerializer, TeamReadinessSerializer, TeamSerializer, WorkflowMemberPoolSerializer, WorkflowMemberSerializer, WorkflowMemberWriteSerializer, WorkflowSerializer, WorkflowWriteSerializer
from .services import StageSequenceError, TeamActionError, WorkflowActionError, deactivate_team, remove_section_member, remove_team_member, remove_workflow_member, route_team, team_member_summaries, validate_team, workflow_member_pool


def _managed_team_ids(user) -> set[int] | None:
    """The team ids ``user`` may manage, or ``None`` for an unrestricted caller.

    ``None`` for HR keeps the queryset filters off the hot path: a manager's
    scope is a small explicit set, HR's is "everything". Every viewset below
    filters through this, so a manager can neither list, read, nor write a team
    (or a workflow or a section membership) that is not theirs.
    """
    if not user or not user.is_authenticated:
        return set()
    if user.role == User.Role.HR or getattr(user, "is_superuser", False):
        return None
    from roles.services import managed_team_ids_for

    return set(managed_team_ids_for(user))

class WorkflowViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """HR-only workflow configuration: read, create, and edit.

    A workflow is written on its own here because a team may own several of
    them and HR configures each separately — create the replacement chain, name
    its stages, and point the team at it when it is ready. Ownership is checked
    by the serializer and the service: a workflow belongs to the team it was
    created for, and a write that would adopt somebody else's chain is refused
    rather than silently re-routing a team.

    ``GET /workflows/?team=<id>`` is the team's workflow listing, which is how
    the team screen finds every chain it owns without reading them all.
    """

    serializer_class = WorkflowSerializer
    permission_classes = [permissions.IsAuthenticated, IsHROrTeamManager]
    # ``delete`` serves the member-removal action only; a workflow itself is
    # removed with its team and is never deleted through this view.
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.action in ("create", "partial_update", "update"):
            return WorkflowWriteSerializer
        return WorkflowSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["actor"] = self.request.user
        return context

    @action(detail=True, methods=["get", "post"], url_path="members")
    def members(self, request, *args, **kwargs):
        """List this workflow's normal members, or add one team member to it.

        Membership is written through the eligibility service, so a person who
        is not on the workflow's team is refused here with the same message the
        pool screen would show — the picker and the write agree because they
        read the same rule.
        """
        workflow = self.get_object()
        if request.method == "POST":
            serializer = WorkflowMemberWriteSerializer(
                data=request.data,
                context={**self.get_serializer_context(), "workflow": workflow},
            )
            serializer.is_valid(raise_exception=True)
            try:
                member = serializer.save()
            except WorkflowMemberError as exc:
                return Response(
                    {exc.field: [exc.message]}, status=status.HTTP_400_BAD_REQUEST
                )
            except IntegrityError as exc:
                # Concurrent assign of the same person: the unique constraints
                # on (workflow, user) and (team, user) are the backstop behind
                # the service-level eligibility check.
                return Response(
                    {"user": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST
                )
            return Response(
                WorkflowMemberSerializer(member).data,
                status=status.HTTP_201_CREATED,
            )
        members = workflow.workflow_members.select_related(
            "user", "team", "added_by"
        ).order_by("user__first_name", "user__last_name", "user_id")
        return Response(WorkflowMemberSerializer(members, many=True).data)

    @action(
        detail=True,
        methods=["delete"],
        url_path="members/(?P<user_id>[^/.]+)",
    )
    def remove_member(self, request, *args, **kwargs):
        """Remove one normal member from this workflow's pool."""
        workflow = self.get_object()
        user_id = positive_int(kwargs["user_id"], "user_id")
        member = WorkflowMember.objects.filter(
            workflow=workflow, user_id=user_id
        ).first()
        if member is None:
            return Response(
                {"user": ["That person is not a normal member of this workflow."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            remove_workflow_member(member=member, actor=request.user)
        except WorkflowMemberError as exc:
            return Response(
                {exc.field: [exc.message]}, status=status.HTTP_409_CONFLICT
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_queryset(self):
        queryset = Workflow.objects.select_related("team").prefetch_related(
            "sections__approver_role", "sections__members__user"
        )
        managed = _managed_team_ids(self.request.user)
        if managed is not None:
            queryset = queryset.filter(team_id__in=managed)
        if self.action != "list":
            return queryset.order_by("name")
        team = self.request.query_params.get("team")
        if team:
            queryset = queryset.filter(team_id=positive_int(team, "team"))
        routing = self.request.query_params.get("routing")
        if routing == "1":
            queryset = queryset.filter(routed_by__isnull=False)
        elif routing == "0":
            queryset = queryset.filter(routed_by__isnull=True)
        return queryset.order_by("name")

    def _write_response(self, workflow):
        return Response(
            WorkflowSerializer(
                workflow, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_201_CREATED,
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            workflow = serializer.save()
        except (WorkflowActionError, StageSequenceError, WorkflowMemberError) as exc:
            field = getattr(exc, "field", "detail")
            message = getattr(exc, "message", str(exc))
            return Response(
                {field: [message]}, status=status.HTTP_400_BAD_REQUEST
            )
        return self._write_response(workflow)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", True)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        try:
            workflow = serializer.save()
        except (WorkflowActionError, StageSequenceError, WorkflowMemberError) as exc:
            field = getattr(exc, "field", "detail")
            message = getattr(exc, "message", str(exc))
            return Response(
                {field: [message]}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            WorkflowSerializer(
                workflow, context=self.get_serializer_context()
            ).data
        )



class SectionMemberViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Who has acted for a section, and the appointment of its approver.

    Appointing somebody is its own atomic, audited action rather than part of a
    whole-workflow write, so changing one step's approver cannot silently rewrite
    the rest of the chain. ``POST`` appoints the one person a step routes to —
    setting :attr:`Section.approver` and opening the effective-dated period that
    records it — and ``DELETE`` closes that period and leaves the step
    unstaffed.

    A step has exactly one approver, so appointing somebody new closes the
    outgoing person's period in the same transaction. Two open periods on one
    step would make "who holds this step" answerable two ways.

    The default view is the people who can act *now*. ``?history=1`` widens it to
    every period, closed ones included, because a membership row is a record of
    who was entitled to act and when — and a chain that once had an approver must
    still be explainable after they have gone.
    """

    serializer_class = SectionMemberSerializer
    permission_classes = [permissions.IsAuthenticated, IsHROrTeamManager]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_serializer_class(self):
        # Reads want the dates and the "is this in force right now" flag; writes
        # are the smaller payload the service actually takes.
        if self.action == "create":
            return SectionMemberWriteSerializer
        return SectionMemberSerializer

    def get_queryset(self):
        params = self.request.query_params
        queryset = (
            SectionMember.all_objects
            if params.get("history") == "1"
            else SectionMember.objects
        ).select_related("section", "section__workflow", "user")
        managed = _managed_team_ids(self.request.user)
        if managed is not None:
            queryset = queryset.filter(section__workflow__team_id__in=managed)
        section = params.get("section")
        if section:
            queryset = queryset.filter(section_id=positive_int(section, "section"))
        workflow = params.get("workflow")
        if workflow:
            queryset = queryset.filter(
                section__workflow_id=positive_int(workflow, "workflow")
            )
        user = params.get("user")
        if user:
            queryset = queryset.filter(user_id=positive_int(user, "user"))
        return queryset.order_by("section__order", "user__last_name")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["actor"] = self.request.user
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            membership = serializer.save()
        except TeamActionError as exc:
            return Response(
                {exc.field: [exc.message]}, status=status.HTTP_400_BAD_REQUEST
            )
        except ValidationError as exc:
            return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            SectionMemberSerializer(
                membership, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        # Closing a membership can legitimately be refused — a period that has
        # not started yet has to be removed outright instead of "ended", and a
        # caller may pass an end date before the start.
        try:
            remove_section_member(membership=self.get_object(), actor=request.user)
        except TeamActionError as exc:
            return Response(
                {exc.field: [exc.message]}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


