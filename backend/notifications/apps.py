from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    name = 'notifications'

    def ready(self):
<<<<<<< HEAD
        """Connect the submission-signal receiver (Unit 22, section 4)."""
        from leave.signals import leave_application_submitted

        from .subscribers import on_application_submitted

        leave_application_submitted.connect(
            on_application_submitted,
            dispatch_uid="notifications.on_application_submitted",
        )
=======
        """Connect the composers to their commit buses.

        The approval-bus consumer is registered here; the cancellation-bus
        consumer is connected by :mod:`notifications.tasks` at import time,
        because that module's callers already need it and Django's ``ready()``
        ordering is not something to depend on.
        """
        from notifications.services import register_decision_email_consumer

        register_decision_email_consumer()
>>>>>>> feature/plans-teams
