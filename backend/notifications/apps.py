from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    name = 'notifications'

    def ready(self):
        """Connect the submission-signal receiver (Unit 22, section 4)."""
        from leave.signals import leave_application_submitted

        from .subscribers import on_application_submitted

        leave_application_submitted.connect(
            on_application_submitted,
            dispatch_uid="notifications.on_application_submitted",
        )