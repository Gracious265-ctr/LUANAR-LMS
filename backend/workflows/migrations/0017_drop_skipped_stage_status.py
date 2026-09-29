"""Drop the ``skipped`` stage status.

A stage used to be bypassed when it resolved to the applicant: the chain started
*after* their step, and the bypassed row was kept as ``skipped`` so the chain
stayed contiguous. Sections replace that. The applicant is removed from the
eligibility snapshot of every section they sit on, the chain always starts at
section one, and a section with nobody left to act refuses the submission — so
there is no longer any way for a stage to be skipped, and a status nothing can
produce is a lie waiting to be believed by a query.

The choice list is what changes here; the column itself is untouched, so this is
a metadata-only alter with no data step and no table rewrite. Any historic row
still holding ``skipped`` (an application decided before sections) keeps the
value: it records what actually happened to that application, and rewriting it
would rewrite history. Such rows are inert — no code path reads the status any
more, and the tracking provider renders an unrecognised state as ``upcoming``.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workflows", "0016_require_team_workflow"),
    ]

    operations = [
        migrations.AlterField(
            model_name="applicationstage",
            name="status",
            field=models.CharField(
                choices=[
                    ("waiting", "Waiting"),
                    ("pending", "Pending action"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                    ("correction_requested", "Correction requested"),
                    ("superseded", "Superseded by resubmission"),
                    ("cancelled", "Cancelled"),
                ],
                default="waiting",
                max_length=20,
            ),
        ),
    ]
