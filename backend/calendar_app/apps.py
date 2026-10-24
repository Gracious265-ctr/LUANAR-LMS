from django.apps import AppConfig


class CalendarAppConfig(AppConfig):
    """The institution-wide calendar: financial years, holidays, events.

    The package is named ``calendar_app`` rather than ``calendar`` so it does
    not shadow the standard-library ``calendar`` module (refinement unit 07,
    recorded as an adaptation in the progress tracker).
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "calendar_app"
    verbose_name = "Calendar"
