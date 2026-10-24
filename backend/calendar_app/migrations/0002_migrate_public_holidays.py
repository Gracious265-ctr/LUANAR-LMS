"""Move ``leave.PublicHoliday`` rows into ``calendar_app.Holiday`` (unit 07).

The old rows are concrete dates with no recurrence or observed-shift semantics,
so they migrate as one-off, non-shifting holidays — a date HR already configured
must keep meaning exactly that date. The reverse re-creates the rows one for one.

``leave``'s subsequent ``DeleteModel`` migration declares a dependency on this
one so the copy always runs before the old table is dropped.
"""

from django.db import migrations


def copy_public_holidays_forward(apps, schema_editor):
    PublicHoliday = apps.get_model("leave", "PublicHoliday")
    Holiday = apps.get_model("calendar_app", "Holiday")

    for public_holiday in PublicHoliday.objects.all():
        Holiday.objects.get_or_create(
            date=public_holiday.date,
            financial_year=None,
            defaults={
                "name": public_holiday.name,
                "is_recurring": False,
                "observed_shift": False,
            },
        )


def copy_public_holidays_backward(apps, schema_editor):
    PublicHoliday = apps.get_model("leave", "PublicHoliday")
    Holiday = apps.get_model("calendar_app", "Holiday")

    for holiday in Holiday.objects.filter(financial_year__isnull=True):
        PublicHoliday.objects.get_or_create(
            date=holiday.date,
            defaults={"name": holiday.name},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("calendar_app", "0001_initial"),
        ("leave", "0023_alter_leaveapplication_current_stage"),
    ]

    operations = [
        migrations.RunPython(
            copy_public_holidays_forward,
            copy_public_holidays_backward,
        ),
    ]
