"""Django signal fired when a leave application is submitted.

Fired on commit (``transaction.on_commit``) so receivers never observe a half-
persisted submission. No receivers exist in Unit 14; later units (routing,
notifications, adjustments) connect here.
"""

from django.dispatch import Signal

leave_application_submitted = Signal()