"""Copy stages and team memberships into sections, and seed the eligibility snapshot.

Step 2 of 3, and the only one that decides anything row by row. It runs after
0013 (the tables exist) and before 0015 (the old tables are dropped), which is
what makes it reversible and lets the application run against either shape
depending on how far the sequence has been applied.

What it does, in order:

1. **One section per workflow stage.** Same ``order``, same ``approver_role``,
   and named after the role's label so the sequence still reads sensibly in the
   admin while HR gives the steps real names.

2. **One member per (section, person)**, taken from the ``TeamMember`` rows of
   whichever teams pointed at that workflow with that role. This is the
   behaviour-preserving step: a stage that resolved to one person becomes a
   section with that one member, so nothing about an existing configuration
   changes just by running the migration.

   A workflow shared by more than one team is a real possibility —
   ``Team.workflow`` is a plain foreign key, so two teams can point at one
   workflow and previously resolve the same role to *different* people. Sections
   belong to the workflow, not the team, so that difference cannot be
   represented: the members merge into one set and every team then routes
   through the same people. The condition is counted and raised as a warning
   rather than silently merged, because HR needs to know.

3. **An eligibility snapshot for every existing application stage**, naming the
   person who was already responsible for it. Without this an application that
   is mid-flight would have a pending stage nobody may act on, and would be
   stuck forever. The old code guaranteed that person was never the applicant,
   so the snapshot is self-approval-free by construction.

4. **``section_ref`` on every application stage**, where the originating
   workflow can still be traced through the applicant's team. This field is
   traceability only — behaviour is read from the snapshotted role fields — so a
   stage whose team or workflow has since been changed away is left null rather
   than guessed at, exactly as the pre-sections rows already are.

The reverse removes the sections, which cascades the members and the eligibility
rows, and restores ``assigned_approver``'s not-null guarantee is *not* attempted:
by this point 0015 has not run, so the column is already nullable and the old
code would simply be re-run against the old tables, which 0013 left intact.
"""

from django.db import migrations


def _warn(message: str) -> None:
    print(f"[0014_backfill_sections] {message}")


def forwards(apps, schema_editor):
    Workflow = apps.get_model("chains", "Workflow")
    WorkflowStage = apps.get_model("chains", "WorkflowStage")
    Team = apps.get_model("chains", "Team")
    TeamMember = apps.get_model("chains", "TeamMember")
    Section = apps.get_model("chains", "Section")
    SectionMember = apps.get_model("chains", "SectionMember")
    ApplicationStage = apps.get_model("chains", "ApplicationStage")
    ApplicationStageApprover = apps.get_model(
        "chains", "ApplicationStageApprover"
    )
    stage_to_section: dict[int, int] = {}

    # 1 + 2: a section per stage, and its members from the teams using it.
    for stage in WorkflowStage.objects.order_by("workflow_id", "order").iterator():
        role = stage.approver_role
        section = Section.objects.create(
            workflow_id=stage.workflow_id,
            name=role.label,
            order=stage.order,
            approver_role_id=role.pk,
        )
        stage_to_section[stage.pk] = section.pk

        teams = list(Team.objects.filter(workflow_id=stage.workflow_id))
        if len(teams) > 1:
            _warn(
                f"workflow_id={stage.workflow_id} is used by {len(teams)} teams "
                f"({', '.join(t.name for t in teams)}). Sections belong to the "
                f"workflow, so their members merge into one set; all of those "
                f"teams will now route the '{role.label}' step through the same "
                f"people. Give each team its own workflow to keep them distinct."
            )

        seen_users: set[int] = set()
        for membership in TeamMember.objects.filter(
            team__workflow_id=stage.workflow_id, role_id=role.pk
        ).order_by("user_id"):
            if membership.user_id in seen_users:
                continue
            seen_users.add(membership.user_id)
            SectionMember.objects.create(
                section_id=section.pk, user_id=membership.user_id
            )

    # 3: an eligibility snapshot for every stage that already exists.
    for stage in ApplicationStage.objects.exclude(
        assigned_approver=None
    ).order_by("id").iterator():
        ApplicationStageApprover.objects.get_or_create(
            stage_id=stage.pk, user_id=stage.assigned_approver_id
        )

    # 4: point each stage at the section it came from, where traceable.
    untraced = 0
    for stage in (
        ApplicationStage.objects.select_related(
            "application__employee__employee_profile"
        )
        .order_by("id")
        .iterator()
    ):
        profile = getattr(stage.application.employee, "employee_profile", None)
        team_id = profile.team_id if profile else None
        workflow_id = (
            Team.objects.filter(pk=team_id)
            .values_list("workflow_id", flat=True)
            .first()
            if team_id is not None
            else None
        )
        if workflow_id is None:
            untraced += 1
            continue
        section = Section.objects.filter(
            workflow_id=workflow_id, order=stage.stage_order
        ).first()
        if section is None:
            untraced += 1
            continue
        stage.section_ref_id = section.pk
        stage.save(update_fields=["section_ref_id"])

    if untraced:
        _warn(
            f"{untraced} application stage(s) could not be traced back to a "
            f"section (the applicant's team or its workflow has changed). Their "
            f"section_ref is left null; the snapshotted role fields still govern "
            f"their behaviour, so this is traceability only."
        )


def backwards(apps, schema_editor):
    """Remove the sections; the eligibility and membership rows cascade."""
    Section = apps.get_model("chains", "Section")
    ApplicationStage = apps.get_model("chains", "ApplicationStage")

    ApplicationStage.objects.exclude(section_ref=None).update(section_ref=None)
    deleted, _ = Section.objects.all().delete()
    _warn(f"removed {deleted} section-related row(s)")


class Migration(migrations.Migration):

    dependencies = [
        ("chains", "0013_sections"),
        # Step 4 reads the applicant's team to trace a stage back to a section,
        # so this needs EmployeeProfile.team to exist. users.0005 adds that
        # field and already depends on workflows.0010, which is an ancestor of
        # 0013 — so this edge cannot form a cycle, it just stops 0014 being free
        # to run before users.0005.
        ("users", "0005_employeeprofile_team"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
