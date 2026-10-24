# Model move state transition (no DB changes)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("roles", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[],
        ),
    ]
