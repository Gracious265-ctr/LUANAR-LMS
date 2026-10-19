"""Re-render approved-leave documents stuck as ``failed`` (or still pending).

The render is a retryable derived artifact: a missing worker, an unreachable
storage backend, or credentials fixed after the fact all leave the row stuck
while the approval itself is already committed. This command re-runs the render
*inline* — no queue worker required — and reports each transition.

    uv run manage.py regenerate_approved_documents
    uv run manage.py regenerate_approved_documents --include-pending
    uv run manage.py regenerate_approved_documents --application <uuid>
    uv run manage.py regenerate_approved_documents --document 3
    uv run manage.py regenerate_approved_documents --dry-run
"""

import uuid

from django.core.management.base import BaseCommand, CommandError

from documents.models import ApprovedLeaveDocument
from documents.tasks import render_approved_document


class Command(BaseCommand):
    help = "Re-render approved-leave documents that are failed (or still pending)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--application",
            help="Only the document for this application id.",
        )
        parser.add_argument(
            "--document",
            type=int,
            help="Only this approved-document id.",
        )
        parser.add_argument(
            "--include-pending",
            action="store_true",
            help="Also re-render rows still pending, not just the failed ones.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List what would be re-rendered without changing anything.",
        )

    def handle(self, *args, **options):
        queryset = ApprovedLeaveDocument.objects.all()
        targeted = False

        if options["document"]:
            targeted = True
            queryset = queryset.filter(pk=options["document"])
        if options["application"]:
            targeted = True
            try:
                application_id = uuid.UUID(str(options["application"]))
            except ValueError:
                raise CommandError(
                    f"--application {options['application']!r} is not a valid id."
                )
            queryset = queryset.filter(application_id=application_id)

        if not targeted:
            statuses = [ApprovedLeaveDocument.Status.FAILED]
            if options["include_pending"]:
                statuses.append(ApprovedLeaveDocument.Status.PENDING)
            queryset = queryset.filter(status__in=statuses)

        documents = list(queryset.order_by("created_at"))
        if not documents:
            self.stdout.write("Nothing to regenerate.")
            return

        regenerated = 0
        still_failed = 0
        for document in documents:
            label = f"document {document.pk} (application {document.application_id})"

            if document.status == ApprovedLeaveDocument.Status.READY:
                self.stdout.write(f"{label}: already ready, skipping.")
                continue

            if options["dry_run"]:
                self.stdout.write(f"{label}: {document.status} -> would re-render.")
                continue

            before = document.status
            after = render_approved_document(document.pk)
            if after == ApprovedLeaveDocument.Status.READY:
                regenerated += 1
                self.stdout.write(self.style.SUCCESS(f"{label}: {before} -> ready."))
            else:
                still_failed += 1
                refreshed = ApprovedLeaveDocument.objects.get(pk=document.pk)
                detail = refreshed.error_message or "no detail"
                self.stdout.write(
                    self.style.WARNING(f"{label}: {before} -> {after} ({detail}).")
                )

        if options["dry_run"]:
            self.stdout.write(f"{len(documents)} document(s) inspected.")
            return

        self.stdout.write(f"Regenerated {regenerated} document(s).")
        if still_failed:
            self.stdout.write(self.style.WARNING(f"{still_failed} still failed."))
