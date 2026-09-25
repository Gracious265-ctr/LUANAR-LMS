"""
Django development settings for LUANAR Leave Management System.
"""

from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

CORS_ALLOW_ALL_ORIGINS = True

# Run queued tasks inline instead of handing them to a ``qcluster`` worker.
#
# Development runs the API and the frontend as two processes, and nothing drains
# the django-q ORM queue unless a third one is started by hand. With the broker
# left async, a task enqueued on commit (``enqueue_approved_document_render``,
# and anything else dispatched that way) sits in ``django_q_ormq`` forever: the
# approved-leave PDF is never rendered, its row stays ``pending``, and the UI
# polls a document that will never appear.
#
# Synchronous execution makes ``async_task`` run the task in-process, so the
# render happens while the approving request is still on its ``on_commit``
# callback and the document is ready by the time the response is written. The
# trade is that the request now waits for the work instead of returning
# immediately — which is the correct trade for a one-page PDF on a dev machine.
#
# This is a development-only setting: production keeps the real async broker and
# a supervised worker. ``config.settings.test`` pins ``sync`` back to ``False``,
# because the suite asserts the enqueue contract rather than the executed task.
Q_CLUSTER = {**Q_CLUSTER, "sync": True}  # noqa: F405
