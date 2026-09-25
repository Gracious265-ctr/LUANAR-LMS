"""Plain-text and minimal HTML email templates keyed by event type (Unit 22).

Each template is a small builder taking a context dict and returning a
:class:`Rendered` (subject, plain-text body, minimal HTML). Context values are
already resolved by the subscribers from the correlated application/request
rows; missing values fall back to friendly placeholders so a half-populated
payload still produces a readable email.
"""

from dataclasses import dataclass
from html import escape

APP_TITLE = "LUANAR Leave Management"


@dataclass(frozen=True)
class Rendered:
    subject: str
    body: str
    html: str


def render(event_type: str, context: dict) -> Rendered:
    """Render the template registered for ``event_type``."""
    try:
        return _REGISTRY[event_type](context)
    except KeyError:
        body = (
            f"Notification from {APP_TITLE}.\n\n"
            + "\n".join(f"{k}: {v}" for k, v in context.items() if v not in (None, ""))
        )
        return Rendered(subject="Notification", body=body, html=_html_wrap(body))


def _builder(event_type):
    def decorate(builder):
        _REGISTRY[event_type] = builder
        return builder

    return decorate


_REGISTRY = {}


def _html_wrap(text: str) -> str:
    lines = "".join(f"<p>{escape(line)}</p>" for line in text.splitlines() if line)
    return (
        f'<div style="font-family:Arial,sans-serif;line-height:1.5">'
        f"<h2>{APP_TITLE}</h2>{lines}<p><small>This is an automated "
        f"notification — please do not reply to this email.</small></p></div>"
    )


def _lines(*rows) -> str:
    return "\n".join(row for row in rows if row)


# --- leave.application.submitted -------------------------------------------------
@_builder("leave.application.submitted")
def _leave_application_submitted(context: dict) -> Rendered:
    body = _lines(
        "A new leave application has been submitted and assigned for approval.",
        "",
        f"Applicant: {context['applicant']}",
        f"Reference: {context['reference_number']}",
        f"Leave type: {context['leave_type']}",
        f"Dates: {context['dates']}",
    )
    return Rendered(
        subject=f"New leave application {context['reference_number']} "
        f"({context['leave_type']})",
        body=body,
        html=_html_wrap(body),
    )


# --- approval events -------------------------------------------------------------
@_builder("approval.stage_assigned")
def _approval_stage_assigned(context: dict) -> Rendered:
    body = _lines(
        f"Leave application {context['reference_number']} now requires your "
        f"approval at the {context['stage']} stage.",
        "",
        f"Applicant: {context['applicant']}",
        f"Leave type: {context['leave_type']}",
        f"Dates: {context['dates']}",
        "You can review and decide in the Approvals queue.",
    )
    return Rendered(
        subject=f"Approval required: {context['reference_number']} "
        f"({context['leave_type']})",
        body=body,
        html=_html_wrap(body),
    )


@_builder("approval.decision_recorded")
def _approval_decision_recorded(context: dict) -> Rendered:
    action_label = {
        "reject": "rejected",
        "return_for_correction": "returned for correction",
    }.get(context.get("action"), f"marked {context.get('action')}")
    body = _lines(
        f"Your leave application {context['reference_number']} "
        f"({context['leave_type']}) was {action_label}.",
        "",
        f"Decision by: {context['approver']}",
        f"Comment: {context['comment']}",
        f"Current status: {context['status']}",
    )
    return Rendered(
        subject=f"Update on {context['reference_number']}: {action_label}",
        body=body,
        html=_html_wrap(body),
    )


@_builder("approval.application_finalised")
def _approval_application_finalised(context: dict) -> Rendered:
    status = context.get("status")
    if status == "approved":
        line1 = (
            f"Congratulations — your leave application "
            f"{context['reference_number']} ({context['leave_type']}) "
            f"has been fully approved."
        )
        subject = f"Leave approved: {context['reference_number']}"
    else:
        line1 = (
            f"Your leave application {context['reference_number']} "
            f"({context['leave_type']}) has been finalised: "
            f"{status or 'decided'}."
        )
        subject = f"Leave finalised: {context['reference_number']}"
    body = _lines(
        line1,
        "",
        f"Dates: {context['dates']}",
        "You can view the application in your dashboard.",
    )
    return Rendered(subject=subject, body=body, html=_html_wrap(body))


# --- cancellation events ---------------------------------------------------------
@_builder("cancellation.requested")
def _cancellation_requested(context: dict) -> Rendered:
    body = _lines(
        f"{context['applicant']} has requested to cancel leave application "
        f"{context['reference_number']}.",
        "",
        f"Reason: {context['reason']}",
        "The request is waiting for approval in the cancellation queue.",
    )
    return Rendered(
        subject=f"Cancellation request: {context['reference_number']}",
        body=body,
        html=_html_wrap(body),
    )


@_builder("cancellation.withdrawn")
def _cancellation_withdrawn(context: dict) -> Rendered:
    body = _lines(
        f"Your cancellation request for {context['reference_number']} has been "
        f"withdrawn. No changes were made to the application.",
    )
    return Rendered(
        subject=f"Cancellation withdrawn: {context['reference_number']}",
        body=body,
        html=_html_wrap(body),
    )


@_builder("cancellation.stage_approved")
def _cancellation_stage_approved(context: dict) -> Rendered:
    body = _lines(
        f"Stage {context['stage_order']} of the cancellation request for "
        f"{context['reference_number']} was approved.",
    )
    return Rendered(
        subject=f"Cancellation stage approved: {context['reference_number']}",
        body=body,
        html=_html_wrap(body),
    )


@_builder("cancellation.approved")
def _cancellation_approved(context: dict) -> Rendered:
    body = _lines(
        f"The cancellation request for leave application "
        f"{context['reference_number']} was approved. The leave is now cancelled.",
        "",
        f"Days restored: {context['balance_restored_days']}",
    )
    return Rendered(
        subject=f"Cancellation approved: {context['reference_number']}",
        body=body,
        html=_html_wrap(body),
    )


@_builder("cancellation.rejected")
def _cancellation_rejected(context: dict) -> Rendered:
    body = _lines(
        f"The cancellation request for leave application "
        f"{context['reference_number']} was rejected.",
        "",
        f"Comment: {context['comment']}",
        "No changes were made to the application.",
    )
    return Rendered(
        subject=f"Cancellation rejected: {context['reference_number']}",
        body=body,
        html=_html_wrap(body),
    )


# --- delegation events -----------------------------------------------------------
@_builder("delegation.approved")
def _delegation_approved(context: dict) -> Rendered:
    body = _lines(
        f"Delegation approved: {context['approver']} to {context['delegate']}.",
        "",
        f"Period: {context['dates']}",
        f"Reason: {context['decision_reason']}",
    )
    return Rendered(
        subject=f"Delegation approved: {context['approver']} → {context['delegate']}",
        body=body,
        html=_html_wrap(body),
    )


@_builder("delegation.rejected")
def _delegation_rejected(context: dict) -> Rendered:
    body = _lines(
        f"Your delegation request ({context['approver']}) was rejected.",
        "",
        f"Reason: {context['decision_reason']}",
    )
    return Rendered(
        subject=f"Delegation rejected: {context['approver']}",
        body=body,
        html=_html_wrap(body),
    )


@_builder("delegation.cancelled")
def _delegation_cancelled(context: dict) -> Rendered:
    body = _lines(
        f"Delegation cancelled: {context['approver']} to {context['delegate']}.",
        "",
        f"Reason: {context['decision_reason']}",
    )
    return Rendered(
        subject=f"Delegation cancelled: {context['approver']}",
        body=body,
        html=_html_wrap(body),
    )


# --- reassignment event ----------------------------------------------------------
@_builder("reassignment.created")
def _reassignment_created(context: dict) -> Rendered:
    body = _lines(
        f"Pending leave application {context['reference_number']} was "
        f"reassigned to {context['to_approver']}.",
        "",
        f"From: {context['from_approver']}",
        f"Reason: {context['reason']}",
    )
    return Rendered(
        subject=f"Application reassigned: {context['reference_number']}",
        body=body,
        html=_html_wrap(body),
    )