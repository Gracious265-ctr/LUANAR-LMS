"""Who may see whose documents — the documents module's read scope.

One predicate, shared by the supporting- and approved-document lists, so the
two lists can never disagree about which employees a viewer covers:

- HR (and superusers) cover the whole institution.
- A designated team manager covers the employees on the teams they manage,
  *plus* themselves.
- Everyone else covers only themselves.

The answer is a set of user ids the document querysets filter their
``application__employee`` against. ``None`` means "no filter" — HR's whole
institution — so a caller must branch on it rather than treating it as an empty
set.
"""

from users.models import User


def visible_employee_ids(user) -> set[int] | None:
    """The user ids whose documents ``user`` may read, or ``None`` for all.

    ``None`` is HR's institution-wide scope, not an empty set: a caller filters
    only when this is not ``None``.
    """
    if not getattr(user, "is_authenticated", False):
        return set()
    if user.role == User.Role.HR or getattr(user, "is_superuser", False):
        return None

    from roles.services import managed_team_ids_for
    from users.models import EmployeeProfile

    team_ids = managed_team_ids_for(user)
    ids = {user.pk}
    if team_ids:
        ids.update(
            EmployeeProfile.objects.filter(team_id__in=team_ids).values_list(
                "user_id", flat=True
            )
        )
    return ids
