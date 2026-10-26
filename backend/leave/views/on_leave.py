"""The On Leave endpoint.

``GET /api/v1/leave/on-leave/`` answers "whose approved leave may I see, and
when are they away". The scope is the backend's decision (``leave.on_leave``),
so this view only parses the two filters the screen offers and shapes nothing:

* ``?q=`` narrows the rows to a name or email match;
* ``?include_past=true`` adds returned leave after the current and upcoming
  rows — the default answers "who is away", not "what is on file".

Every authenticated account may call it; what comes back depends on the rung of
the visibility ladder they stand on. There is no employee id to supply, so there
is nothing here a caller could point at somebody outside their scope.
"""

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..on_leave import MAX_SEARCH_LENGTH, on_leave_payload

#: The values a caller may send as "yes" for ``include_past``. A query string
#: has no booleans, and a checkbox that submits nothing must not mean "true".
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


class OnLeaveView(APIView):
    """Approved leave within the signed-in caller's visibility scope."""

    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "head", "options"]

    def get(self, request):
        include_past = (
            request.query_params.get("include_past", "").strip().lower()
            in TRUE_VALUES
        )
        query = (request.query_params.get("q") or "").strip()[:MAX_SEARCH_LENGTH]
        return Response(
            on_leave_payload(
                user=request.user,
                include_past=include_past,
                query=query,
            ),
            status=status.HTTP_200_OK,
        )
