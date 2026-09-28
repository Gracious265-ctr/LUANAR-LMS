"""HR reassignment emails.

The same discipline as :mod:`notifications.tests_delegations`, applied to the
reassignment subject family: a real ``Reassignment`` row, a real service call
(which emits on commit), and assertions against the durable append-only
``NotificationOutbox`` rows plus the console backend's ``mail.outbox``.
"""

from __future__ import annotations

from datetime import timedelta
from unittest import mock
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from leave.models import LeaveApplication
from notifications.models import NotificationOutbox
from notifications.reassignments import (
    APPLICATION_REASSIGNED,
    FROM_APPROVER,
    TO_APPROVER,
    send_reassignment_email,
)
from workflows.models import Reassignment
from workflows.services import ReassignmentError, reassign_application
from workflows.testing import make_approver

User = get_user_model()


def make_user(role, email, *, active=True) -> User:
    user = User.objects.create_user(
        username=f"user-{uuid4().hex[:8]}",
        email=email,
        password="testpass123",
        first_name="Test",
        last_name=email.split("@")[0],
        role=role,
    )
    if active:
        user.is_active = True
        user.save(update_fields=["is_active"])
    return user


class ReassignmentEmailTests(TestCase):
    def setUp(self):
        self.hr = make_user(User.Role.HR, "hr@notify.test")
        self.employee = make_user(User.Role.EMPLOYEE, "emp@notify.test")
        self.dean = make_approver("dean", username="dean@notify.test")
        self.hod = make_approver("hod", username="hod@notify.test")

    def _app(self, approver=None) -> LeaveApplication:
        return LeaveApplication.objects.create(
            employee=self.employee,
            current_approver=approver,
            status=LeaveApplication.Status.SUBMITTED,
            reference_number="LUANAR-2026-0099",
            start_date=timezone.localdate() + timedelta(days=7),
            end_date=timezone.localdate() + timedelta(days=9),
            calculated_days=3,
            reason="Family emergency",
            submitted_at=timezone.now(),
        )

    def _reassignment(self, *, from_approver=None, to_approver=None) -> Reassignment:
        return Reassignment.objects.create(
            application=self._app(approver=from_approver),
            from_approver=from_approver,
            to_approver=to_approver or self.hod,
            reason="Approver is on fieldwork",
            decided_by=self.hr,
        )

    def _rows(self, reassignment):
        return list(
            NotificationOutbox.objects.filter(
                reassignment=reassignment
            ).order_by("role_label")
        )

    def test_both_approvers_are_notified(self):
        reassignment = self._reassignment(from_approver=self.dean)

        send_reassignment_email(reassignment.pk)

        rows = self._rows(reassignment)
        self.assertEqual(
            [row.role_label for row in rows], [FROM_APPROVER, TO_APPROVER]
        )
        self.assertEqual(
            {row.recipient_email for row in rows}, {self.dean.email, self.hod.email}
        )
        self.assertTrue(all(row.state == "sent" for row in rows))
        self.assertEqual(len(mail.outbox), 2)

    def test_each_side_hears_about_its_own_half_of_the_move(self):
        reassignment = self._reassignment(from_approver=self.dean)

        send_reassignment_email(reassignment.pk)

        new_mail = next(m for m in mail.outbox if m.to == [self.hod.email])
        old_mail = next(m for m in mail.outbox if m.to == [self.dean.email])
        self.assertIn("have been assigned", new_mail.body)
        self.assertIn("reassigned away from you", old_mail.body)
        for message in (new_mail, old_mail):
            self.assertIn("LUANAR-2026-0099", message.subject)
            self.assertIn("Approver is on fieldwork", message.body)

    def test_initial_assignment_notifies_only_the_new_approver(self):
        reassignment = self._reassignment(from_approver=None)

        send_reassignment_email(reassignment.pk)

        rows = self._rows(reassignment)
        self.assertEqual([row.role_label for row in rows], [TO_APPROVER])
        self.assertEqual(rows[0].recipient_email, self.hod.email)
        self.assertEqual(len(mail.outbox), 1)

    def test_re_emitting_is_idempotent(self):
        reassignment = self._reassignment(from_approver=self.dean)

        send_reassignment_email(reassignment.pk)
        send_reassignment_email(reassignment.pk)

        self.assertEqual(len(self._rows(reassignment)), 2)
        self.assertEqual(len(mail.outbox), 2)

    def test_two_reassignments_of_one_application_both_notify(self):
        """The outbox row hangs off the reassignment, not the application.

        An application can be reassigned several times in one submission cycle,
        so an application-keyed row would make the second mail silently
        idempotent-suppress against the first.
        """
        app = self._app(approver=self.dean)
        first = reassign_application(
            application=app, to_approver=self.hod, actor=self.hr, reason="First"
        )
        send_reassignment_email(first.pk)
        app.refresh_from_db()
        second = reassign_application(
            application=app, to_approver=self.dean, actor=self.hr, reason="Second"
        )
        send_reassignment_email(second.pk)

        self.assertEqual(len(self._rows(first)), 2)
        self.assertEqual(len(self._rows(second)), 2)
        self.assertEqual(
            NotificationOutbox.objects.filter(
                application=app, kind=APPLICATION_REASSIGNED
            ).count(),
            0,
        )

    def test_a_dead_backend_records_failed_without_raising(self):
        reassignment = self._reassignment(from_approver=self.dean)

        with mock.patch(
            "notifications.reassignments.send_mail",
            side_effect=OSError("mail backend is down"),
        ):
            send_reassignment_email(reassignment.pk)

        rows = self._rows(reassignment)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row.state == "failed" for row in rows))
        self.assertIn("mail backend is down", rows[0].error)

    def test_a_failing_backend_never_breaks_the_intervention(self):
        app = self._app(approver=self.dean)

        with mock.patch(
            "notifications.reassignments.send_mail",
            side_effect=OSError("mail backend is down"),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                reassign = reassign_application(
                    application=app,
                    to_approver=self.hod,
                    actor=self.hr,
                    reason="Fieldwork",
                )

        app.refresh_from_db()
        self.assertEqual(app.current_approver_id, self.hod.pk)
        self.assertTrue(Reassignment.objects.filter(pk=reassign.pk).exists())

    def test_a_user_without_an_email_is_skipped(self):
        self.hod.email = ""
        self.hod.save(update_fields=["email"])
        reassignment = self._reassignment(from_approver=self.dean)

        send_reassignment_email(reassignment.pk)

        self.assertEqual(
            [row.role_label for row in self._rows(reassignment)], [FROM_APPROVER]
        )

    def test_an_unresolvable_reassignment_raises_the_seam_error(self):
        from notifications.services import NotificationSeamUnresolvableError

        with self.assertRaises(NotificationSeamUnresolvableError):
            send_reassignment_email(Reassignment.objects.none().values_list(
                "pk", flat=True
            ).first() or 999999)

    def test_the_outbox_rejects_two_subjects_on_one_row(self):
        reassignment = self._reassignment(from_approver=self.dean)
        with self.assertRaises(IntegrityError):
            NotificationOutbox.objects.create(
                application=reassignment.application,
                reassignment=reassignment,
                kind=APPLICATION_REASSIGNED,
                recipient_email="x@test.luanar",
            )

    def test_the_outbox_rejects_no_subject(self):
        with self.assertRaises(IntegrityError):
            NotificationOutbox.objects.create(
                kind=APPLICATION_REASSIGNED,
                recipient_email="x@test.luanar",
            )


class ReassignmentOutboxWiringTests(TestCase):
    """``reassign_application`` emits on commit; a rejected one emits nothing."""

    def setUp(self):
        self.hr = make_user(User.Role.HR, "hr-wire@notify.test")
        self.employee = make_user(User.Role.EMPLOYEE, "emp-wire@notify.test")
        self.dean = make_approver("dean", username="dean-wire@notify.test")
        self.hod = make_approver("hod", username="hod-wire@notify.test")

    def _app(self, approver=None) -> LeaveApplication:
        return LeaveApplication.objects.create(
            employee=self.employee,
            current_approver=approver,
            status=LeaveApplication.Status.SUBMITTED,
            reference_number="LUANAR-2026-0100",
            start_date=timezone.localdate() + timedelta(days=3),
            end_date=timezone.localdate() + timedelta(days=4),
            calculated_days=2,
            reason="Family emergency",
            submitted_at=timezone.now(),
        )

    def test_the_service_emits_one_row_per_side(self):
        app = self._app(approver=self.dean)

        with self.captureOnCommitCallbacks(execute=True):
            reassign_application(
                application=app, to_approver=self.hod, actor=self.hr, reason="Away"
            )

        self.assertEqual(
            set(
                NotificationOutbox.objects.filter(kind=APPLICATION_REASSIGNED).values_list(
                    "role_label", flat=True
                )
            ),
            {FROM_APPROVER, TO_APPROVER},
        )

    def test_nothing_is_sent_before_commit(self):
        app = self._app(approver=self.dean)

        with mock.patch.object(
            transaction, "on_commit"
        ) as on_commit:
            reassign_application(
                application=app, to_approver=self.hod, actor=self.hr, reason="Away"
            )

        on_commit.assert_called_once()
        self.assertEqual(
            NotificationOutbox.objects.filter(kind=APPLICATION_REASSIGNED).count(), 0
        )
        self.assertEqual(mail.outbox, [])

    def test_a_rejected_reassignment_emits_nothing(self):
        app = self._app(approver=self.dean)

        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(ReassignmentError):
                reassign_application(
                    application=app, to_approver=self.dean, actor=self.hr, reason="x"
                )

        self.assertEqual(
            NotificationOutbox.objects.filter(kind=APPLICATION_REASSIGNED).count(), 0
        )
        self.assertEqual(mail.outbox, [])
