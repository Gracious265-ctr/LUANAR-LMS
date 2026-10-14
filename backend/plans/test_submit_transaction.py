"""``submit_plan`` must own its transaction.

Regression test for the 500 on ``POST /api/plans/<id>/submit/``. The service
locks the plan with ``select_for_update()``, which raises
``TransactionManagementError`` unless it runs inside an atomic block, and
``PlanSubmitAPIView`` catches only ``PlanNotFoundError``,
``PlanNotSubmittableError`` and ``PlanValidationFailedError`` — so the error
escaped as a 500.

``TestCase`` can never catch this: its own wrapping transaction makes the lock
legal, which is why the HTTP-level submit tests stayed green while production
broke. ``TransactionTestCase`` runs without one, like a real request.
"""

import uuid

from django.db import connection
from django.test import TransactionTestCase

from leave.tests.stubs import make_user
from plans.services import PlanNotFoundError, submit_plan


class SubmitPlanTransactionTests(TransactionTestCase):
    def test_locks_the_plan_without_being_handed_a_transaction(self):
        user = make_user(username="plan-transaction@test.luanar")

        # Reaching ``PlanNotFoundError`` means ``select_for_update()`` was
        # evaluated. Without the service's own transaction this raised
        # ``TransactionManagementError`` at exactly that point instead.
        with self.assertRaises(PlanNotFoundError):
            submit_plan(user=user, plan_id=uuid.uuid4())

    def test_the_test_itself_starts_outside_a_transaction(self):
        """Keeps the first test honest.

        Rewriting this class as ``TestCase`` would silently re-mask the bug,
        because the runner's wrapping transaction would make the lock legal
        again. This asserts the property the regression actually depends on.
        """
        self.assertFalse(connection.in_atomic_block)
