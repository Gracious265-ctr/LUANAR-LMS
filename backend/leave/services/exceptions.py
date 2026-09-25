"""Finalisation errors for the leave app's services package (Unit 25 D4).

``leave/services/finalise.py`` was written in Unit 23 against this module, but
the module was never created, which left ``finalise.py`` unimportable and its
``record_deduction`` writer unwired. Unit 25 wires the annual-balance deduction
(D4) and therefore needs these types to exist.

The document-generation half of Unit 23 remains deferred to Unit 23b; only the
balance errors are needed now.
"""


class LeaveTypeNotResolvableError(Exception):
    """The annual-balance deduction decision could not be resolved.

    Raised when the submitted ``rules_snapshot`` carries no
    ``deducts_annual_balance`` entry, so no safe deduction decision exists.
    """


class ApplicationFinalisationError(Exception):
    """An approved application cannot be finalised as it stands.

    Raised when the deduction inputs the ledger needs (working days, financial
    year) are missing from the application.
    """


class DeductionAlreadyRecordedError(Exception):
    """A deduction for this application already exists in the ledger.

    Exported for the idempotency surface; the writer itself uses
    ``get_or_create`` plus the ``one_deduction_per_application`` constraint and
    does not raise this.
    """
