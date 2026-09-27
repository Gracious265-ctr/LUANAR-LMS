from django.apps import AppConfig


class LeaveConfig(AppConfig):
    name = 'leave'

    def ready(self):
        from leave import holiday_refresh  # noqa: F401
