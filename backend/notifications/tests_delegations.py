"""Delegation lifecycle emails.

The same discipline as :mod:`notifications.tests`, applied to the delegation
subject family: a real ``Delegation`` row, a real service call (which emits on
commit), and assertions against the durable append-only ``NotificationOutbox``
rows plus the console backend's ``mail.outbox``.
"""

from __future__ import annotations

from datetime import timedelta
from unittest import mock
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import transaction
from django.test import TestCase
from django.utils import timezone

from notifications.delegations import (
    APPROVER,
    DELEGATE,
    DELEGATION_APPROVED,
    DELEGATION_CANCELLED,
    DELEGATION_REJECTED,
    DELEGATION_REQUESTED,
    send_delegation_email,
)
from notifications.models import NotificationOutbox, NotificationOutboxLockedError
from workflows.models import Delegation
from workflows.services import DelegationActionError
from workflows.testing import make_approver

User = get_user_model()


def make_user(role, email) -> User:
    return User.objects.create_user(
        username=f"user-{uuid4().hex[:8]}",
        email=email,
        password="testpass123",
        first_name="Test",
        last_name=email.split("@")[0],
        role=role,
    )


class DelegationEmailTests(TestCase):
    def setUp(self):
        self.hr = make_user(User.Role.HR, "hr@notify.test")
        self.dean = make_approver("dean", username="dean@notify.test")
        self.hod = make_approver("hod", username="hod@notify.test")
        self.today = timezone.localdate()

    def _delegation(self, **overrides) -> Delegation:
        defaults = {
            "approver": self.dean,
            "delegate": None,
            "starts_on": self.today,
            "ends_on": None,
            "requested_by": self.dean,
            "status": Delegation.Status.REQUESTED,
        }
        defaults.update(overrides)
        return Delegation.objects.create(**defaults)

    def _rows(self, delegation):
        return list(
            NotificationOutbox.objects.filter(delegation=delegation).order_by(
                "role_label"
            )
        )

    def test_request_notifies_only_a_nominated_delegate(self):
        delegation = self._delegation(delegate=self.hod)
        send_delegation_email(delegation.pk, DELEGATION_REQUESTED)

        rows = self._rows(delegation)
        self.assertEqual([row.role_label for row in rows], [DELEGATE])
        self.assertEqual(rows[0].recipient_email, self.hod.email)
        self.assertEqual(rows[0].state, "sent")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.dean.get_full_name(), mail.outbox[0].subject)

    def test_request_without_a_nomination_sends_nothing(self):
        delegation = self._delegation()
        send_delegation_email(delegation.pk, DELEGATION_REQUESTED)

        self.assertEqual(self._rows(delegation), [])
        self.assertEqual(mail.outbox, [])

    def test_approval_notifies_both_sides(self):
        delegation = self._delegation(
            delegate=self.hod, status=Delegation.Status.APPROVED
        )
        send_delegation_email(delegation.pk, DELEGATION_APPROVED)

        rows = self._rows(delegation)
        self.assertEqual([row.role_label for row in rows], [APPROVER, DELEGATE])
        self.assertEqual(
            {row.recipient_email for row in rows}, {self.dean.email, self.hod.email}
        )
        self.assertEqual(len(mail.outbox), 2)
        # The delegate's copy tells them they are now acting.
        delegate_mail = next(m for m in mail.outbox if m.to == [self.hod.email])
        self.assertIn("acting as delegate", delegate_mail.body)

    def test_rejection_notifies_the_approver_and_the_nominee(self):
        delegation = self._delegation(
            delegate=self.hod, status=Delegation.Status.REJECTED
        )
        send_delegation_email(delegation.pk, DELEGATION_REJECTED)

        self.assertEqual(
            [row.role_label for row in self._rows(delegation)], [APPROVER, DELEGATE]
        )

    def test_cancellation_notifies_the_approver_when_no_delegate_was_set(self):
        delegation = self._delegation(status=Delegation.Status.CANCELLED)
        send_delegation_email(delegation.pk, DELEGATION_CANCELLED)

        rows = self._rows(delegation)
        self.assertEqual([row.role_label for row in rows], [APPROVER])
        self.assertEqual(rows[0].recipient_email, self.dean.email)

    def test_re_emitting_one_kind_is_idempotent(self):
        delegation = self._delegation(delegate=self.hod)
        send_delegation_email(delegation.pk, DELEGATION_REQUESTED)
        send_delegation_email(delegation.pk, DELEGATION_REQUESTED)

        self.assertEqual(len(self._rows(delegation)), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_distinct_kinds_each_get_a_row(self):
        delegation = self._delegation(delegate=self.hod)
        send_delegation_email(delegation.pk, DELEGATION_REQUESTED)
        send_delegation_email(delegation.pk, DELEGATION_APPROVED)

        self.assertEqual(len(self._rows(delegation)), 3)

    def test_body_names_the_period_and_the_hr_reason(self):
        delegation = self._delegation(
            delegate=self.hod,
            status=Delegation.Status.APPROVED,
            starts_on=self.today,
            ends_on=self.today + timedelta(days=4),
            decision_reason="Dean is on study leave",
        )
        send_delegation_email(delegation.pk, DELEGATION_APPROVED)

        body = mail.outbox[0].body
        self.assertIn(self.today.isoformat(), body)
        self.assertIn((self.today + timedelta(days=4)).isoformat(), body)
        self.assertIn("Dean is on study leave", body)

    def test_send_failure_records_failed_and_isolates(self):
        delegation = self._delegation(delegate=self.hod)
        with mock.patch(
            "notifications.delegations.send_mail", side_effect=RuntimeError("smtp down")
        ):
            send_delegation_email(delegation.pk, DELEGATION_REQUESTED)

        row = self._rows(delegation)[0]
        self.assertEqual(row.state, "failed")
        self.assertIn("smtp down", row.error)

    def test_delegation_outbox_rows_are_append_only(self):
        delegation = self._delegation(delegate=self.hod)
        send_delegation_email(delegation.pk, DELEGATION_REQUESTED)
        row = self._rows(delegation)[0]
        with self.assertRaises(NotificationOutboxLockedError):
            NotificationOutbox.objects.filter(pk=row.pk).update(state="pending")
        with self.assertRaises(NotificationOutboxLockedError):
            NotificationOutbox.objects.filter(pk=row.pk).delete()

    def test_notify_waits_for_the_commit(self):
        """A rolled-back decision must not mail anybody."""
        delegation = self._delegation(delegate=self.hod)
        try:
            with transaction.atomic():
                transaction.on_commit(
                    lambda: send_delegation_email(delegation.pk, DELEGATION_REQUESTED)
                )
                raise RuntimeError("rollback")
        except RuntimeError:
            pass

        self.assertEqual(self._rows(delegation), [])
        self.assertEqual(mail.outbox, [])


class DelegationOutboxWiringTests(TestCase):
    """The three decision services emit; a failed action emits nothing."""

    def setUp(self):
        self.hr = make_user(User.Role.HR, "hr-wire@notify.test")
        self.dean = make_approver("dean", username="dean-wire@notify.test")
        self.hod = make_approver("hod", username="hod-wire@notify.test")
        self.today = timezone.localdate()

    def _requested(self) -> Delegation:
        return Delegation.objects.create(
            approver=self.dean,
            starts_on=self.today,
            requested_by=self.dean,
            status=Delegation.Status.REQUESTED,
        )

    def test_approve_emits_to_both_sides(self):
        from workflows.services import approve_delegation

        delegation = self._requested()
        with self.captureOnCommitCallbacks(execute=True):
            approve_delegation(
                delegation, self.hr, {"delegate": self.hod, "decision_reason": "ok"}
            )

        self.assertEqual(
            set(
                NotificationOutbox.objects.filter(delegation=delegation).values_list(
                    "kind", flat=True
                )
            ),
            {DELEGATION_APPROVED},
        )

    def test_reject_emits(self):
        from workflows.services import reject_delegation

        delegation = self._requested()
        with self.captureOnCommitCallbacks(execute=True):
            reject_delegation(delegation, self.hr, {"decision_reason": "No"})

        self.assertTrue(
            NotificationOutbox.objects.filter(
                delegation=delegation, kind=DELEGATION_REJECTED
            ).exists()
        )

    def test_cancel_emits(self):
        from workflows.services import cancel_delegation

        delegation = Delegation.objects.create(
            approver=self.dean,
            delegate=self.hod,
            starts_on=self.today,
            requested_by=self.dean,
            status=Delegation.Status.APPROVED,
        )
        with self.captureOnCommitCallbacks(execute=True):
            cancel_delegation(delegation, self.hr, {"decision_reason": "Not needed"})

        self.assertTrue(
            NotificationOutbox.objects.filter(
                delegation=delegation, kind=DELEGATION_CANCELLED
            ).exists()
        )

    def test_failed_decision_emits_nothing(self):
        from workflows.services import approve_delegation

        delegation = self._requested()
        with self.assertRaises(DelegationActionError):
            approve_delegation(
                delegation, self.hr, {"delegate": self.hod, "decision_reason": ""}
            )

        self.assertEqual(
            NotificationOutbox.objects.filter(delegation=delegation).count(), 0
        )

    def test_hr_create_on_behalf_emits_to_the_nominated_delegate(self):
        from rest_framework.test import APIClient

        client = APIClient()  # type: ignore[assignment]
        client.force_authenticate(user=self.hr)
        with self.captureOnCommitCallbacks(execute=True):
            response = client.post(
                "/api/v1/delegations/",
                {
                    "approver": self.dean.pk,
                    "delegate": self.hod.pk,
                    "starts_on": self.today.isoformat(),
                },
                format="json",
            )
        self.assertEqual(response.status_code, 201)
        delegation = Delegation.objects.get(pk=response.data["id"])
        self.assertTrue(
            NotificationOutbox.objects.filter(
                delegation=delegation, kind=DELEGATION_REQUESTED, role_label=DELEGATE
            ).exists()
        )

    def test_approver_self_service_create_emits(self):
        from rest_framework.test import APIClient

        client = APIClient()  # type: ignore[assignment]
        client.force_authenticate(user=self.dean)
        # No ``approver`` key: the backend forces the requester, and so does the
        # row's delegate notification.
        with self.captureOnCommitCallbacks(execute=True):
            response = client.post(
                "/api/v1/delegations/",
                {"delegate": self.hod.pk, "starts_on": self.today.isoformat()},
                format="json",
            )
        self.assertEqual(response.status_code, 201)
        delegation = Delegation.objects.get(pk=response.data["id"])
        self.assertEqual(delegation.approver, self.dean)
        self.assertTrue(
            NotificationOutbox.objects.filter(
                delegation=delegation, kind=DELEGATION_REQUESTED, role_label=DELEGATE
            ).exists()
        )
