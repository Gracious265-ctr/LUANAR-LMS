"""Domain errors for Unit 16 approval workflow and decisions."""


class WorkflowValidationError(Exception):
    """The workflow returned by a provider (or its approvers) is invalid.

    ``field`` mirrors the API field the error belongs to; ``message`` is the
    human-readable explanation. Raised so submission fails cleanly before any
    stage or decision data is written (invariant 12.7).
    """

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


class NotAllowed(Exception):
    """The actor is not authorized to decide on this application.

    ``reason`` is a short code: ``application_closed``, ``not_current_stage``
    or ``already_decided``. Maps to HTTP 403.
    """

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class StageChanged(Exception):
    """The stage changed since the caller fetched it (optimistic lock).

    Maps to HTTP 409; nothing is ever decided twice.
    """


class DecisionValidationError(Exception):
    """The decision payload is invalid (bad action, empty comment, too long).

    ``field`` and ``message`` map to an HTTP 400 field error.
    """

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message