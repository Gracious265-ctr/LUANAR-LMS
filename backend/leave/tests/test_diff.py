"""Unit tests for the resubmission diff engine (Unit 17, section 4).

``compute_changes`` is pure and dependency-free, so these tests only exercise
snapshot dicts — no database, no fixtures. They pin the exact ``Changes``
shape returned to the edit page preview and the approver payload.
"""

from datetime import date

from django.test import SimpleTestCase

from leave.diff import compute_changes

DAILY_SNAPSHOT = {
    "leave_type": {"id": 1, "name": "Annual Leave"},
    "start_date": date(2026, 11, 2),
    "end_date": date(2026, 11, 6),
    "working_days": 5,
    "reason": "Family visit",
    "documents": [],
}


def snapshot(**overrides):
    payload = {
        "leave_type": {"id": 1, "name": "Annual Leave"},
        "start_date": date(2026, 11, 2),
        "end_date": date(2026, 11, 6),
        "working_days": 5,
        "reason": "Family visit",
        "documents": [],
    }
    payload.update(overrides)
    return payload


class ComputeChangesTests(SimpleTestCase):
    def test_identical_snapshots_produce_no_changes(self):
        result = compute_changes(snapshot(), snapshot())
        self.assertFalse(result["has_changes"])
        self.assertEqual(result["fields"], [])
        self.assertEqual(
            result["documents"], {"added": [], "removed": [], "replaced": []}
        )

    def test_reason_change_is_reported(self):
        result = compute_changes(
            snapshot(reason="Family visit"),
            snapshot(reason="Family visit — urgent"),
        )
        self.assertTrue(result["has_changes"])
        field = next(f for f in result["fields"] if f["field"] == "reason")
        self.assertEqual(field["label"], "Reason")
        self.assertEqual(field["before"], "Family visit")
        self.assertEqual(field["after"], "Family visit — urgent")

    def test_whitespace_only_reason_change_is_ignored(self):
        result = compute_changes(
            snapshot(reason="Family visit"),
            snapshot(reason="  Family visit  "),
        )
        self.assertFalse(result["has_changes"])

    def test_dates_and_working_days_are_reported_with_labels(self):
        result = compute_changes(
            snapshot(start_date=date(2026, 11, 2), working_days=5),
            snapshot(start_date=date(2026, 11, 3), working_days=4),
        )
        by_field = {f["field"]: f for f in result["fields"]}
        self.assertEqual(by_field["start_date"]["label"], "Start date")
        self.assertEqual(by_field["start_date"]["before"], "2026-11-02")
        self.assertEqual(by_field["start_date"]["after"], "2026-11-03")
        self.assertEqual(by_field["working_days"]["before"], 5)
        self.assertEqual(by_field["working_days"]["after"], 4)

    def test_leave_type_change_is_labelled_by_name(self):
        result = compute_changes(
            snapshot(leave_type={"id": 1, "name": "Annual Leave"}),
            snapshot(leave_type={"id": 2, "name": "Compassionate Leave"}),
        )
        field = next(f for f in result["fields"] if f["field"] == "leave_type")
        self.assertEqual(field["label"], "Leave type")
        self.assertEqual(field["before"], "Annual Leave")
        self.assertEqual(field["after"], "Compassionate Leave")

    def test_leave_type_change_matches_by_id_despite_same_name(self):
        result = compute_changes(
            snapshot(leave_type={"id": 1, "name": "Study Leave"}),
            snapshot(leave_type={"id": 2, "name": "Study Leave"}),
        )
        field = next(f for f in result["fields"] if f["field"] == "leave_type")
        self.assertEqual(field["before"], "Study Leave")
        self.assertEqual(field["after"], "Study Leave")


def doc(doc_id, name):
    return {
        "document_id": doc_id,
        "name": name,
        "size_bytes": 100,
        "content_type": "application/pdf",
    }


class ComputeChangesDocumentTests(SimpleTestCase):
    def test_added_document_is_reported(self):
        result = compute_changes(
            snapshot(documents=[doc("a", "cert.pdf")]),
            snapshot(documents=[doc("a", "cert.pdf"), doc("b", "note.pdf")]),
        )
        self.assertEqual(result["documents"]["added"], [{"name": "note.pdf"}])
        self.assertEqual(result["documents"]["removed"], [])
        self.assertEqual(result["documents"]["replaced"], [])

    def test_removed_document_is_reported_when_not_replaced(self):
        result = compute_changes(
            snapshot(documents=[doc("a", "cert.pdf")]),
            snapshot(
                documents=[],
                retired=[
                    {
                        "document_id": "a",
                        "name": "cert.pdf",
                        "retire_reason": "removed",
                        "replaced_by_id": None,
                    }
                ],
            ),
        )
        self.assertEqual(result["documents"]["removed"], [{"name": "cert.pdf"}])

    def test_replaced_document_reports_old_and_new_name(self):
        result = compute_changes(
            snapshot(documents=[doc("a", "cert.pdf")]),
            snapshot(
                documents=[doc("b", "cert-v2.pdf")],
                retired=[
                    {
                        "document_id": "a",
                        "name": "cert.pdf",
                        "retire_reason": "replaced",
                        "replaced_by_id": "b",
                    }
                ],
            ),
        )
        self.assertEqual(result["documents"]["removed"], [])
        self.assertEqual(
            result["documents"]["replaced"],
            [{"old_name": "cert.pdf", "new_name": "cert-v2.pdf"}],
        )
        # the replacement endpoint must not double-count as "added"
        self.assertEqual(result["documents"]["added"], [])

    def test_replacement_endpoint_is_not_reported_as_added(self):
        result = compute_changes(
            snapshot(documents=[]),
            snapshot(
                documents=[doc("b", "cert-v2.pdf"), doc("c", "note.pdf")],
                retired=[
                    {
                        "document_id": "a",
                        "name": "cert.pdf",
                        "retire_reason": "replaced",
                        "replaced_by_id": "b",
                    }
                ],
            ),
        )
        added = {item["name"] for item in result["documents"]["added"]}
        self.assertEqual(added, {"cert-v2.pdf", "note.pdf"})

    def test_two_step_replacement_chain(self):
        # ``a`` is in the previous snapshot and ``a→b→c``: the replacement
        # is reported as cert.pdf → c.pdf and neither b nor c appears as
        # added (c is the endpoint of the chain).
        result = compute_changes(
            snapshot(documents=[doc("a", "cert.pdf")]),
            snapshot(
                documents=[doc("c", "c.pdf")],
                retired=[
                    {
                        "document_id": "a",
                        "name": "cert.pdf",
                        "retire_reason": "replaced",
                        "replaced_by_id": "b",
                    },
                    {
                        "document_id": "b",
                        "name": "cert-v2.pdf",
                        "retire_reason": "replaced",
                        "replaced_by_id": "c",
                    },
                ],
            ),
        )
        self.assertEqual(
            result["documents"]["replaced"],
            [{"old_name": "cert.pdf", "new_name": "c.pdf"}],
        )
        self.assertEqual(result["documents"]["added"], [])
        self.assertEqual(result["documents"]["removed"], [])

    def test_broken_replacement_chain_falls_back_to_removed(self):
        # ``a`` claims to be replaced by ``b``, but ``b`` is retired too and
        # points nowhere: the chain does not end on an active document.
        result = compute_changes(
            snapshot(documents=[doc("a", "cert.pdf")]),
            snapshot(
                documents=[],
                retired=[
                    {
                        "document_id": "a",
                        "name": "cert.pdf",
                        "retire_reason": "replaced",
                        "replaced_by_id": "b",
                    },
                    {
                        "document_id": "b",
                        "name": "cert-v2.pdf",
                        "retire_reason": "removed",
                        "replaced_by_id": None,
                    },
                ],
            ),
        )
        self.assertEqual(result["documents"]["removed"], [{"name": "cert.pdf"}])
        self.assertEqual(result["documents"]["replaced"], [])

    def test_document_changes_alone_set_has_changes(self):
        result = compute_changes(
            snapshot(documents=[]),
            snapshot(documents=[doc("b", "note.pdf")]),
        )
        self.assertTrue(result["has_changes"])