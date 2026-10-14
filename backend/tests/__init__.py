"""Unit 25 — one composed end-to-end journey across the real services (D1, D9).

Every earlier unit tested its own slice, so a fully green suite still said
nothing about whether the slices were *connected*. This module drives the real
services against a real HR-configured approval chain and asserts the whole
journey at once. It is the unit that found the four seams Unit 25 fixed:

* ``decide()`` flipped the status to ``APPROVED`` but never wrote the annual
  balance deduction (D4), and the constraint that makes the write idempotent
  did not exist (D3).
* The event-kind condition was inverted, so a rejection announced
  ``application_finalised`` (D5).
* HR's organization-wide view filtered ``SUBMITTED`` only, hiding every
  application that had actually been finalized (D6).
* Employee edits were rejected for ``correction_required`` although the
  frontend already offered the edit (D7).

Per D10 the journey calls real services rather than the HTTP layer; the API is
used only where the HTTP contract is itself the thing under test (HR's
finalized read, the employee's own application list).
"""
