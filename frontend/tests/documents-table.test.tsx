import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  DocumentsTable,
  type DocumentRow,
} from "@/components/documents/documents-table";

const rows: DocumentRow[] = [
  {
    id: "doc-1",
    fileName: "leave-approval.pdf",
    fileSizeLabel: "12.4 KB",
    employeeName: "Jane Dean",
    reference: "LV-2026-27-000001",
    dateLabel: "01 Oct 2026, 10:00",
    statusLabel: "Ready",
    statusTone: "approved",
    href: "https://storage.test/doc-1",
    unavailableLabel: "Not available",
  },
  {
    id: "doc-2",
    fileName: "medical-certificate.pdf",
    fileSizeLabel: "40 KB",
    employeeName: "Ruth Member",
    reference: "LV-2026-27-000002",
    dateLabel: "02 Oct 2026, 09:00",
    statusLabel: "Ready",
    statusTone: "approved",
    href: "",
    unavailableLabel: "Not available",
  },
];

describe("DocumentsTable", () => {
  it("narrows both lists by file, employee, reference, or status", () => {
    render(
      <DocumentsTable
        rows={rows}
        showsApplicant
        kind="approved"
        dateHeading="Approved"
        searchLabel="Search approved documents"
      />
    );

    fireEvent.change(
      screen.getByRole("searchbox", { name: "Search approved documents" }),
      { target: { value: "jane" } }
    );

    expect(screen.getByText("leave-approval.pdf")).toBeInTheDocument();
    expect(screen.queryByText("medical-certificate.pdf")).toBeNull();
  });

  it("explains that a search hid every row instead of claiming the list is empty", () => {
    render(
      <DocumentsTable
        rows={rows}
        showsApplicant
        kind="supporting"
        dateHeading="Uploaded"
        searchLabel="Search supporting documents"
      />
    );

    fireEvent.change(
      screen.getByRole("searchbox", { name: "Search supporting documents" }),
      { target: { value: "nothing here" } }
    );

    expect(
      screen.getByText("No documents match this search")
    ).toBeInTheDocument();
  });
});
