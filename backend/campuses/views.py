from rest_framework import mixins, permissions, viewsets
from rest_framework.exceptions import ValidationError

from .models import Campus, CampusRoleAssignment
from .serializers import CampusRoleAssignmentSerializer, CampusSerializer
from .permissions import IsHROnly

from users.models import User


def _positive_int(value, field_name):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError({field_name: "Must be an integer."}) from exc
    if parsed < 1:
        raise ValidationError({field_name: "Must be a positive integer."})
    return parsed


class CampusViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """HR-managed campus reference data (no hard delete).

    ``PROTECT`` on Team.campus is deliberate: deleting a campus that a team
    points at would silently change what "this team's campus" means, so a
    campus is only ever deactivated.
    """

    serializer_class = CampusSerializer
    permission_classes = [permissions.IsAuthenticated, IsHROnly]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = Campus.objects.all()
        if self.request.query_params.get("include_inactive") != "1":
            queryset = queryset.filter(is_active=True)
        return queryset.order_by("name")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["actor"] = self.request.user
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            campus = serializer.save()
        except CampusActionError as exc:
            return Response(
                {exc.field: [exc.message]}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            CampusSerializer(campus, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.pop("partial", True)
        )
        serializer.is_valid(raise_exception=True)
        try:
            campus = serializer.save()
        except CampusActionError as exc:
            return Response(
                {exc.field: [exc.message]}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            CampusSerializer(campus, context=self.get_serializer_context()).data
        )
