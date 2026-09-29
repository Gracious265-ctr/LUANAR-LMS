"""Give the Team its own lifecycle and give membership a history.

Three changes, all in service of one idea: a team's configuration is only
meaningful once HR has said it is in force, and the record of how the
configuration looked at the time is not ours to rewrite.

**``Team.is_active`` → ``Team.status``.** A boolean cannot say "being built
yet", which is the state a team is actually in for most of its life — HR names
it, wires its sections, and only then should an employee's submission follow it.
Those half-finished teams used to be indistinguishable from live ones, so a team
with no approvers anywhere still looked ready and only failed at submission
time. ``status`` is ``draft`` / ``active`` / ``inactive`` and replaces the
boolean outright rather than sitting beside it: two fields that both claim to
say whether a team routes is how they come to disagree.

The mapping preserves meaning for every existing row: an active team becomes
``active`` and an inactive one becomes ``inactive``. A team that was switched on
but had no effective date keeps routing exactly as before, because a blank
``effective_from`` on the team means "operative from activation", not "not yet
operative". No row is turned into a draft behind HR's back, and the only new
drafts are the ones created from here on.

**Team department and effective window.** Department is the field that stops two
active teams being configured to cover the same ground without HR having said so,
and the effective window is what retires a team for routing on a date HR chose
while keeping its configuration. Both are nullable/blank, so nothing that
worked stops working.

**``SectionMember`` is effective-dated.** The uniqueness constraint moves from
"(section, user) at most once" to "(section, user) at most one *open* period",
and the default manager now returns only open rows. A row closed by
``remove_section_member`` is kept with an ``effective_to`` date instead of being
deleted. Existing rows all become open periods starting the day they were
created: they are the memberships that are working today, and dating them from
the day they were appointed rather than the day this migration ran keeps
"since when has this person been able to approve?" answerable. The partial index
is what makes the constraint cheap — the database checks the open row, not the
history.
"""

from django.db import migrations, models
from django.utils import timezone


def carry_over_team_lifecycle(apps, schema_editor):
    """Turn each team's boolean into the status that meant the same thing.

    Runs between adding ``status`` and dropping ``is_active`` so both columns
    exist at once and no team is ever without a lifecycle value.
    """
    Team = apps.get_model("workflows", "Team")
    Team.objects.filter(is_active=True).update(status="active")
    Team.objects.filter(is_active=False).update(status="inactive")


def date_existing_memberships(apps, schema_editor):
    """Give every existing membership an open period from its appointment.

    ``effective_from`` is the date the row was created — the day the person
    actually became eligible to act — and ``effective_to`` stays null, so the
    default manager keeps returning exactly the set it returned before. The rows
    are walked in Python because a date truncating a timestamp is a
    ``__date`` transform, and transforms are not portable in an ``UPDATE``; the
    table holds one row per person per section, not a history yet, so this is
    small by construction.
    """
    SectionMember = apps.get_model("workflows", "SectionMember")
    for membership in SectionMember.objects.all().iterator():
        membership.effective_from = (
            membership.created_at.date()
            if membership.created_at
            else timezone.localdate()
        )
        membership.save(update_fields=["effective_from"])


class Migration(migrations.Migration):

    dependencies = [
        ("workflows", "0017_drop_skipped_stage_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="team",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("active", "Active"),
                    ("inactive", "Inactive"),
                ],
                default="draft",
                help_text=(
                    "Draft teams do not route. Only an active team inside its "
                    "effective dates routes an application."
                ),
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="team",
            name="department",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "The department this team belongs to. Informational — "
                    "routing follows the team, not the department — but it is "
                    "what stops two active teams being configured to cover the "
                    "same department without HR having said so."
                ),
                max_length=200,
            ),
        ),
        migrations.AddField(
            model_name="team",
            name="effective_from",
            field=models.DateField(
                blank=True,
                help_text=(
                    "The first date this team routes applications. Blank means "
                    "active from the moment it is activated."
                ),
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="team",
            name="effective_to",
            field=models.DateField(
                blank=True,
                help_text=(
                    "The last date this team routes applications; blank routes "
                    "indefinitely. Past this date the team is retired for "
                    "routing while its configuration is kept."
                ),
                null=True,
            ),
        ),
        migrations.RunPython(carry_over_team_lifecycle, migrations.RunPython.noop),
        migrations.RemoveField(model_name="team", name="is_active"),
        migrations.AddConstraint(
            model_name="team",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("effective_to__isnull", True),
                    ("effective_from__isnull", True),
                    ("effective_to__gte", models.F("effective_from")),
                    _connector="OR",
                ),
                name="team_effective_window_ordered",
            ),
        ),
        migrations.AddField(
            model_name="sectionmember",
            name="effective_from",
            field=models.DateField(
                default=timezone.localdate,
                help_text=(
                    "The first date this person is eligible to act for the "
                    "section."
                ),
            ),
        ),
        migrations.AddField(
            model_name="sectionmember",
            name="effective_to",
            field=models.DateField(
                blank=True,
                help_text=(
                    "The last date this person is eligible to act for the "
                    "section; blank while the membership is open."
                ),
                null=True,
            ),
        ),
        migrations.RunPython(date_existing_memberships, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="sectionmember",
            name="sectionmember_section_user_unique",
        ),
        migrations.AddConstraint(
            model_name="sectionmember",
            constraint=models.UniqueConstraint(
                condition=models.Q(("effective_to__isnull", True)),
                fields=("section", "user"),
                name="sectionmember_open_section_user_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="sectionmember",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("effective_to__isnull", True),
                    ("effective_to__gte", models.F("effective_from")),
                    _connector="OR",
                ),
                name="sectionmember_effective_window_ordered",
            ),
        ),
        migrations.AlterModelOptions(
            name="sectionmember",
            options={"ordering": ["section", "user", "effective_from"]},
        ),
    ]
