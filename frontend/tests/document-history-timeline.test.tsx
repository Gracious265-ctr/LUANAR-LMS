import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DocumentHistoryTimeline } from "@/components/leave/document-history-timeline";
import type { DocumentHistory } from "@/lib/documents/types";

const history: DocumentHistory = {
  active: [
    {
      id: "doc-2",
      file_path: "leave-documents/abc/doc-2/cert-v2.pdf",
      file_url: "",
      file_name: "cert-v2.pdf",
      file_size: 4096,
      content_type: "application/pdf",
      uploaded_at: "2026-09-21T10:00:00Z",
      status: "active",
      retired_at: null,
      retired_by: null,
      retire_reason: null,
      replaced_by: null,
      replaced_by_name: null,
    },
  ],
  retired: [
    {
      id: "doc-1",
      file_path: "leave-documents/abc/doc-1/cert.pdf",
      file_url: "",
      file_name: "cert.pdf",
      file_size: 2048,
      content_type: "application/pdf",
      uploaded_at: "2026-09-20T09:00:00Z",
      status: "retired",
      retired_at: "2026-09-21T10:00:00Z",
      retired_by: 7,
      retire_reason: "replaced",
      replaced_by: "doc-2",
      replaced_by_name: "cert-v2.pdf",
    },
  ],
  events: [
    {
      id: "evt-1",
      action: "document_uploaded",
      actor_name: "Mary Banda",
      occurred_at: "2026-09-20T09:00:00Z",
      metadata: { file_name: "cert.pdf" },
    },
    {
      id: "evt-2",
      action: "document_replaced",
      actor_name: "Mary Banda",
      occurred_at: "2026-09-21T10:00:00Z",
      metadata: { file_name: "cert.pdf" },
    },
  ],
};

describe("DocumentHistoryTimeline", () => {
  it("renders active and retired document sections", () => {
    render(<DocumentHistoryTimeline history={history} />);

    expect(screen.getByText("Active documents (1)")).toBeInTheDocument();
    expect(
      within(screen.getByText("Active documents (1)").closest("section")!).getByText(
        "cert-v2.pdf"
      )
    ).toBeInTheDocument();
    expect(screen.getByText("Retired documents (1)")).toBeInTheDocument();
    expect(
      within(screen.getByText("Retired documents (1)").closest("section")!).getByText(
        "cert.pdf"
      )
    ).toBeInTheDocument();
    expect(screen.getByText("4.0 KB")).toBeInTheDocument();
  });

  it("marks replaced documents with their replacement name", () => {
    render(<DocumentHistoryTimeline history={history} />);

    expect(
      screen.getByText(/cert-v2\.pdf/, { selector: "span.no-underline" })
    ).toBeInTheDocument();
  });

  it("translates document actions on the activity timeline", () => {
    render(<DocumentHistoryTimeline history={history} />);

    expect(screen.getByText(/Uploaded/)).toBeInTheDocument();
    expect(screen.getByText(/Replaced/)).toBeInTheDocument();
    expect(screen.getAllByText(/Mary Banda/)).toHaveLength(2);
  });

  it("renders empty states", () => {
    render(
      <DocumentHistoryTimeline
        history={{ active: [], retired: [], events: [] }}
      />
    );

    expect(screen.getByText("Active documents (0)")).toBeInTheDocument();
    expect(screen.getByText("No document activity yet.")).toBeInTheDocument();
  });
});