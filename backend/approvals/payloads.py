"""Approver review/list payload builders (Unit 16).

These pure functions translate ``LeaveApplication`` + stage/decision rows into
the exact API payload shapes the spec (section 1) defines. They are read-only
view helpers; every value is derived from already-persisted state.
"""

from __future__ import annotations

from decimal import Decimal

from audit.models import AuditEntry
from audit.services import actor_display_name
from leave.models import GradeEntitlement, LeaveApplication, LeaveType, SupportingDocument
from leave.services import active_financial_year, financial_year_label

from approvals.models import ApplicationStage, ApprovalDecision

_VALID_STATES = ("pending", "approved", "rejected", "correction_required", "cancelled")


def _profile(user):
    try:
        return user.employee_profile
    except Exception:
        return None


def list_item(application: LeaveApplication, user) -> dict:
    """One row for the pending/decided lists (spec 1.1/1.2)."""
    decision = latest_user_decision(application, user)
    return {
        "id": str(application.id),
        "reference": application.reference_number,
        "employee_name": application.employee.get_full_name()
        or application.employee.username,
        "team": _team(application),
        "leave_type": leave_type_block(application),
        "start_date": _iso_date(application.start_date),
        "end_date": _iso_date(application.end_date),
        "working_days": application.working_days,
        "submitted_at": _iso(application.submitted_at),
        "status": derived_status(application),
        "submission_cycle": application.submission_cycle,
        "is_resubmission": application.submission_cycle > 1,
        # The pending stage's optimistic-lock version, surfaced so a bulk
        # approval can be built from the list without opening each application
        # (spec 5). Null when the application has left the chain.
        "stage_version": (
            application.current_stage.decision_version
            if application.current_stage_id is not None
            else None
        ),
        "my_decision": (
            {
                "action": decision.action,
                "decided_at": _iso(decision.decided_at),
            }
            if decision
            else None
        ),
    }


def review_payload(application: LeaveApplication, user, view_access) -> dict:
    """The full review payload (spec 1.3). ``view_access`` governs history."""
    from workflows.policies import get_decision_authority

    employee_profile = _profile(application.employee)
    approver_profile = _profile(user)
    history_available, history_scope = _leave_history_scope(
        view_access, employee_profile, approver_profile
    )
    authority = get_decision_authority(user, application)
    return {
        "application": _application_block(application),
        "employee_info": _employee_info(application),
        "rules": _rules_block(application),
        "balance": _balance(application),
        "documents": [
            _document_block(doc)
            for doc in application.documents.filter(status="active")
        ],
        "history": {
            "leave_history": {
                "available": history_available,
                "scope": history_scope,
                "entries": _leave_history_entries(application, history_scope)
                if history_available
                else [],
            },
            "audit_history": _audit_history(application),
        },
        "workflow": _workflow_block(application),
        "my_decision": _my_decision_block(application, user),
        "can_decide": authority.can_decide,
        "decision_restriction": authority.reason,
        "decisions": _decision_list(application),
        "resubmission": _resubmission_block(application),
    }


def briefing_blocks(application: LeaveApplication, user) -> dict:
    """Small derived blocks for the decision response banner."""
    return {
        "status": derived_status(application),
        "reference": application.reference_number,
        "current_stage": _current_stage_block(application),
        "my_decision": _my_decision_block(application, user),
    }


def derived_status(application: LeaveApplication) -> str:
    """Active status; a submitted app with an undecided stage is ``pending``."""
    status = application.status
    if status != LeaveApplication.Status.SUBMITTED:
        return status if status in _VALID_STATES else status
    stage = application.current_stage_id
    if stage is None:
        return "pending"
    return "pending" if application.current_stage.status == "pending" else status


def leave_type_block(application: LeaveApplication) -> dict:
    snapshot = (application.rules_snapshot or {}).get("leave_type")
    if snapshot:
        return {
            "id": snapshot.get("id"),
            "code": snapshot.get("code"),
            "name": snapshot.get("name"),
        }
    row = LeaveType.objects.filter(id=application.leave_type_id).first()
    if row is not None:
        return {"id": row.id, "code": row.code, "name": row.name}
    return {
        "id": application.leave_type_id,
        "code": None,
        "name": f"Leave type #{application.leave_type_id}",
    }


def latest_user_decision(application: LeaveApplication, user) -> ApprovalDecision | None:
    return (
        ApprovalDecision.objects.filter(application=application, approver=user)
        .order_by("-decided_at")
        .first()
    )


def _team(application: LeaveApplication) -> str:
    """The employee's team *name*, or "".

    The team is the reference row an employee's identity is read against, and
    this payload is rendered to an approver as JSON \u2014 so the name is what
    belongs here.
    """
    profile = _profile(application.employee)
    if profile is None or profile.team_id is None:
        return ""
    return profile.team.name


def _application_block(application: LeaveApplication) -> dict:
    return {
        "id": str(application.id),
        "reference": application.reference_number,
        "submission_cycle": application.submission_cycle,
        "start_date": _iso_date(application.start_date),
        "end_date": _iso_date(application.end_date),
        "working_days": application.working_days,
        "calendar_days": application.calendar_days,
        "submitted_at": _iso(application.submitted_at),
        "reason": application.reason,
        "financial_year_label": application.financial_year_label,
    }


def _employee_info(application: LeaveApplication) -> dict:
    user = application.employee
    profile = _profile(user)
    return {
        "name": user.get_full_name() or user.username,
        "designation": (profile.designation if profile else "") or "",
        # The name, not the row: this payload is rendered to an approver, and a
        # Team instance is not something JSON can carry.
        "team": ((profile.team.name if profile and profile.team_id else "") or ""),
        "faculty": (profile.faculty if profile else "") or "",
        "staff_id": None,
        "grade": (profile.grade if profile else "") or "",
        "category": (profile.category if profile else "") or "",
        "appointment_date": (
            _iso_date(profile.appointment_date) if profile else None
        ),
    }


def _rules_block(application: LeaveApplication) -> dict:
    snapshot = application.rules_snapshot or {}
    return {
        "leave_type": leave_type_block(application),
        "holidays": [
            _iso_date(day) if isinstance(day, str) else day
            for day in (snapshot.get("holidays") or [])
        ],
        "working_days": snapshot.get("working_days")
        or application.working_days,
        "calendar_days": snapshot.get("calendar_days")
        or application.calendar_days,
        "min_notice": _snapshot_min_notice(snapshot),
        "requires_document": bool((snapshot.get("leave_type") or {}).get("requires_document")),
        "available_balance": snapshot.get("available_balance"),
        "balance_after_if_approved": snapshot.get(
            "balance_after_if_approved"
        ),
    }


def _snapshot_min_notice(snapshot: dict):
    leave_type = snapshot.get("leave_type") or {}
    return {
        "value": leave_type.get("min_notice"),
        "unit": leave_type.get("min_notice_unit"),
    }


def _balance(application: LeaveApplication) -> dict:
    snapshot = application.rules_snapshot or {}
    available_raw = snapshot.get("available_balance")
    available = Decimal(str(available_raw)) if available_raw not in (None, "") else Decimal(0)
    entitlement = _entitlement_days(application)
    used = None
    if entitlement is not None:
        used = max(Decimal(0), entitlement - available)
    return {
        "entitlement": str(entitlement) if entitlement is not None else None,
        "used": str(used) if used is not None else None,
        "available": str(available),
        "financial_year_label": application.financial_year_label,
    }


def _entitlement_days(application: LeaveApplication) -> Decimal | None:
    profile = _profile(application.employee)
    grade = ((profile.grade if profile else "") or "").strip().upper()
    if not grade:
        return None
    row = (
        GradeEntitlement.objects.filter(grade_start__lte=grade, grade_end__gte=grade)
        .order_by("-effective_from")
        .first()
    )
    if row is not None:
        return Decimal(row.days)
    return _fixture_band_days(grade)


def _fixture_band_days(grade: str) -> Decimal | None:
    bands = (("A", "C", 21), ("D", "G", 24), ("H", "U", 30))
    grade = grade.upper()
    if not (len(grade) == 1 and grade.isalpha() and "A" <= grade <= "Z"):
        return None
    for start, end, days in bands:
        if start <= grade <= end:
            return Decimal(days)
    return None


def _document_block(document: SupportingDocument) -> dict:
    return {
        "id": str(document.id),
        "name": document.file_name,
        "size": document.file_size,
        "content_type": document.content_type,
        "uploaded_at": _iso(document.uploaded_at),
    }


def _leave_history_scope(view_access, employee_profile, approver_profile):
    from workflows.policies import get_leave_history_scope

    return get_leave_history_scope(view_access, employee_profile, approver_profile)


def _leave_history_entries(application: LeaveApplication, scope: str) -> list[dict]:
    qs = LeaveApplication.objects.filter(employee=application.employee).exclude(
        status=LeaveApplication.Status.DRAFT
    )
    if scope == "current_financial_year":
        year = active_financial_year()
        label = (
            financial_year_label(year) if year else application.financial_year_label
        ) or ""
        if label:
            qs = qs.filter(financial_year_label=label)
    entries = []
    for app in qs.exclude(pk=application.pk).order_by("-submitted_at")[:20]:
        entries.append(
            {
                "id": str(app.id),
                "reference": app.reference_number,
                "leave_type": leave_type_block(app),
                "start_date": _iso_date(app.start_date),
                "end_date": _iso_date(app.end_date),
                "working_days": app.working_days,
                "status": derived_status(app),
                "submitted_at": _iso(app.submitted_at),
            }
        )
    return entries


def _audit_history(application: LeaveApplication) -> list[dict]:
    entries = (
        AuditEntry.objects.filter(
            target_type=AuditEntry.TargetType.APPLICATION,
            target_id=str(application.pk),
        )
        .select_related("actor")
        .order_by("created_at")
    )
    return [
        {
            "id": entry.pk,
            "action": entry.action,
            "occurred_at": _iso(entry.created_at),
            # A system-generated entry (e.g. the document render) has no actor;
            # resolving the name here keeps a null actor from 500-ing the whole
            # review payload.
            "actor": actor_display_name(entry.actor),
            "reason": entry.reason,
        }
        for entry in entries
    ]


def _workflow_block(application: LeaveApplication) -> dict:
    cycle = application.workflow_chain_cycle
    stages = list(
        ApplicationStage.objects.filter(
            application=application, submission_cycle=cycle
        )
        .select_related("assigned_approver")
        .order_by("stage_order")
    )
    from .services import acting_approver_id, responsible_approver_id

    responsible_id = responsible_approver_id(application)
    acting_id = acting_approver_id(application)
    stage_payloads = [
        _stage_block(
            stage,
            stage.decisions.order_by("-decided_at").first(),
            responsible_id,
            acting_id,
        )
        for stage in stages
    ]
    current_decision = (
        ApprovalDecision.objects.filter(
            application=application,
            stage__submission_cycle=cycle,
        )
        .select_related("approver")
        .order_by("-decided_at")
        .first()
    )
    return {
        "state": derived_status(application),
        "current_stage": _current_stage_block(application),
        "stages": stage_payloads,
        "current_decision": (
            {
                "action": current_decision.action,
                "role_label": current_decision.role_label,
                "approver_name": current_decision.approver_name
                or (current_decision.approver.get_full_name()
                    or current_decision.approver.username),
                "comment": current_decision.comment,
                "decided_at": _iso(current_decision.decided_at),
            }
            if current_decision
            else None
        ),
    }


def _stage_block(
    stage: ApplicationStage,
    decision: ApprovalDecision | None,
    responsible_id=None,
    acting_id=None,
) -> dict:
    """One stage of the review payload.

    A pending section is not yet owned by anyone: ``assigned_approver`` stays
    null until somebody acts, because several people may be entitled to and the
    first one to act claims it. ``eligible_approvers`` is therefore the honest
    answer for a pending stage — who *could* take it — while ``approver`` is only
    populated once there is someone to name.
    """
    assigned_name = (
        stage.assigned_approver.get_full_name() or stage.assigned_approver.username
        if stage.assigned_approver_id
        else None
    )
    acting_for = None
    approver_name = assigned_name
    if stage.status == ApplicationStage.Status.PENDING and acting_id:
        acting_name = _user_name(acting_id)
        if acting_name:
            approver_name = acting_name
        if responsible_id == stage.assigned_approver_id and acting_id != stage.assigned_approver_id:
            # A delegate covering for the configured approver (D3).
            acting_for = _user_name(responsible_id)
    return {
        "order": stage.stage_order,
        "role": stage.role,
        "role_label": stage.role_label,
        "status": stage.status,
        "submission_cycle": stage.submission_cycle,
        "decision_version": stage.decision_version,
        "assigned_approver": assigned_name,
        "approver": approver_name,
        "acting_for": acting_for,
        # Who was entitled to act, read from the eligibility snapshot taken at
        # submission. A decided step keeps the record of who *could* have acted.
        "eligible_approvers": [
            name
            for name in (_user_name(uid) for uid in stage.eligible_approver_ids())
            if name
        ],
        "assigned_at": _iso(stage.created_at),
        "decided_at": _iso(decision.decided_at if decision else None),
        "comment": decision.comment if decision else None,
        # Why this stage was skipped (Unit 30). Null rather than "" so a client
        # can tell "not skipped" from "skipped for no stated reason", and so the
        # reason shows in the approval history without the stage having to be
        # hidden or dropped from it.
        "skip_reason": stage.skip_reason or None,
    }


def _user_name(pk) -> str | None:
    if pk is None:
        return None
    from users.models import User

    row = (
        User.objects.filter(pk=pk)
        .values("first_name", "last_name", "username")
        .first()
    )
    if row is None:
        return None
    name = f"{row['first_name']} {row['last_name']}".strip()
    return name or row["username"]


def _current_stage_block(application: LeaveApplication) -> dict | None:
    stage = application.current_stage
    if stage is None:
        return None
    next_label = _following_stage_label(application, stage)
    from .services import acting_approver_id, responsible_approver_id

    responsible = responsible_approver_id(application)
    acting = acting_approver_id(application)
    approver_name = _user_name(acting)
    acting_for = _user_name(responsible) if acting and acting != responsible else None
    return {
        "order": stage.stage_order,
        "role": stage.role,
        "role_label": stage.role_label,
        "is_final": stage.is_final,
        "next_role_label": next_label,
        "approver": approver_name,
        "acting_for": acting_for,
    }


def _following_stage_label(application: LeaveApplication, stage) -> str | None:
    """The role label of the stage the application will move to next.

    The chain is contiguous and nothing is ever bypassed, so this is simply the
    next stage by order — the same stage ``decide`` activates. The applicant is
    not something this has to work around: a section they belong to is decided
    by their colleagues, and a section they are the only member of was refused
    at submission.
    """
    following = (
        ApplicationStage.objects.filter(
            application=application,
            submission_cycle=application.workflow_chain_cycle,
            stage_order__gt=stage.stage_order,
        )
        .order_by("stage_order")
    )
    return next((candidate.role_label for candidate in following), None)


def _my_decision_block(application: LeaveApplication, user) -> dict | None:
    decision = latest_user_decision(application, user)
    if decision is None:
        return None
    return {
        "action": decision.action,
        "role_label": decision.role_label,
        "decided_at": _iso(decision.decided_at),
        "comment": decision.comment,
    }


def _decision_list(application: LeaveApplication) -> list[dict]:
    """Every recorded decision across cycles, oldest first (Unit 17).
    The frontend groups these by ``submission_cycle`` to build the per-cycle
    approval history timeline.
    """
    decisions = (
        ApprovalDecision.objects.filter(application=application)
        .select_related("approver")
        .order_by("decided_at", "id")
    )
    return [
        {
            "id": decision.pk,
            "submission_cycle": decision.submission_cycle,
            "action": decision.action,
            "approver_name": decision.approver_name
            or (decision.approver.get_full_name() or decision.approver.username),
            "role_label": decision.role_label,
            "comment": decision.comment,
            "decided_at": _iso(decision.decided_at),
        }
        for decision in decisions
    ]


def _resubmission_block(application: LeaveApplication) -> dict:
    """Resubmission context for the review payload (Unit 17).

    ``changes_since_my_decision`` diffs the current live content against the
    cycle in which the chain was originally created (the snapshot the approvers
    saw), so a returning approver sees exactly what the employee edited.
    """
    if application.submission_cycle <= application.workflow_chain_cycle:
        return {
            "is_resubmission": False,
            "cycle": application.submission_cycle,
            "resubmitted_at": None,
            "changes_since_my_decision": None,
        }
    latest = application.revisions.order_by("-revision_number").first()
    return {
        "is_resubmission": True,
        "cycle": application.submission_cycle,
        "resubmitted_at": _iso(latest.created_at) if latest else None,
        "changes_since_my_decision": _changes_since_my_decision(application),
    }


def _changes_since_my_decision(application: LeaveApplication) -> dict | None:
    baseline = (
        application.revisions.filter(
            revision_number=application.workflow_chain_cycle,
        )
        .order_by("-revision_number")
        .first()
    )
    if baseline is None:
        return None
    from leave.diff import compute_changes

    changes = compute_changes(
        _snapshot_payload(baseline),
        _current_snapshot_payload(application),
    )
    return changes.to_payload() if not changes.is_empty() else None


def _snapshot_payload(revision) -> dict:
    return {
        "leave_type_id": revision.leave_type_id,
        "leave_type_name": revision.leave_type_name,
        "start_date": revision.start_date,
        "end_date": revision.end_date,
        "working_days": revision.working_days,
        "reason": revision.reason,
        "documents": [
            {
                "document_id": doc.get("document_id"),
                "name": doc.get("name"),
            }
            for doc in revision.documents or []
        ],
    }


def _current_snapshot_payload(application: LeaveApplication) -> dict:
    docs = []
    active_docs = application.documents.filter(
        status="active"
    ).select_related("application").order_by("file_name")
    for doc in active_docs:
        replaced_ids = [
            str(retired.id) for retired in doc.replaced_documents.all()
        ]
        docs.append(
            {
                "document_id": str(doc.id),
                "name": doc.file_name,
                "replaces": replaced_ids,
            }
        )
    name = leave_type_block(application).get("name")
    return {
        "leave_type_id": application.leave_type_id,
        "leave_type_name": name,
        "start_date": application.start_date,
        "end_date": application.end_date,
        "working_days": application.working_days,
        "reason": application.reason,
        "documents": docs,
    }


def _iso_date(value):
    return value.isoformat() if value else None


def _iso(value):
    if not value:
        return None
    return value.isoformat().replace("+00:00", "Z")