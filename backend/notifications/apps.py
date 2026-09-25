from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    name = 'notifications'

    def ready(self):
        from notifications.services import register_decision_email_consumer

        register_decision_email_consumer()
