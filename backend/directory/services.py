"""Local-user reconciliation for external organisation records.

The provider speaks external employee ids; the rest of the system speaks
``django.contrib.auth`` users. Until the organisation's real directory
defines a durable key, reconciliation is by email address — the fixture
employees carry the seeded demo users' addresses, so the mapping resolves
today without an ``external_employee_id`` schema change (decision recorded
for refinement unit 05). When a real directory ships, this module is the one
place the mapping changes.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model

from .factory import get_organization_provider


def find_provider_employee_for_user(user, provider=None):
    """Return the provider's ``EmployeeRecord`` for a local user, or None."""
    email = (getattr(user, "email", "") or "").strip().lower()
    if not email:
        return None
    provider = provider or get_organization_provider()
    for record in provider.get_employees():
        if (record.email or "").strip().lower() == email:
            return record
    return None


def get_local_user_for_external_employee(external_employee_id, provider=None):
    """Return the local ``User`` for a provider employee id, or None."""
    if not external_employee_id:
        return None
    provider = provider or get_organization_provider()
    record = provider.get_employee(external_employee_id)
    if record is None:
        return None
    email = (record.email or "").strip().lower()
    if not email:
        return None
    return get_user_model().objects.filter(email__iexact=email).first()
