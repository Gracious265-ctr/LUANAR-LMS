import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DocumentTemplatePreview } from "@/components/hr/document-template-preview";
import type { LeaveDocumentTemplate } from "@/lib/leave-document-template";

const template: LeaveDocumentTemplate = {
  title: "APPROVED LEAVE",
  header: "LILONGWE UNIVERSITY OF AGRICULTURE AND NATURAL RESOURCES",
  intro: "Official opening wording.",
  fields: [
    { key: "reference", label: "Reference" },
    { key: "employee_name", label: "Employee Name" },
  ],
  closing: "Official closing wording.",
  signature_areas: [{ label: "Employee signature" }, { label: "For: Registrar" }],
  footer: "LUANAR",
  available_fields: [
    { key: "reference", label: "Reference", sample: "LV-2026-000123" },
    { key: "employee_name", label: "Employee", sample: "Jane Employee" },
  ],
  updated_at: "2026-09-17T12:00:00Z",
};

describe("DocumentTemplatePreview", () => {
  it("renders the header, title, intro and closing wording", () => {
    render(<DocumentTemplatePreview template={template} />);

    expect(
      screen.getByText("LILONGWE UNIVERSITY OF AGRICULTURE AND NATURAL RESOURCES")
    ).toBeInTheDocument();
    expect(screen.getByText("APPROVED LEAVE")).toBeInTheDocument();
    expect(screen.getByText("Official opening wording.")).toBeInTheDocument();
    expect(screen.getByText("Official closing wording.")).toBeInTheDocument();
  });

  it("renders field labels with sample values in configured order", () => {
    render(<DocumentTemplatePreview template={template} />);

    const preview = screen.getByLabelText("Document template preview");
    const rows = within(preview).getAllByRole("row");
    expect(rows[0].textContent).toContain("Reference");
    expect(rows[0].textContent).toContain("LV-2026-000123");
    expect(rows[1].textContent).toContain("Employee Name");
    expect(rows[1].textContent).toContain("Jane Employee");
  });

  it("renders signature captions", () => {
    render(<DocumentTemplatePreview template={template} />);

    expect(screen.getByText("Employee signature")).toBeInTheDocument();
    expect(screen.getByText("For: Registrar")).toBeInTheDocument();
  });

  it("omits blank wording and empty signature areas", () => {
    const minimal: LeaveDocumentTemplate = {
      ...template,
      header: "",
      intro: "",
      closing: "",
      footer: "",
      signature_areas: [],
    };
    render(<DocumentTemplatePreview template={minimal} />);

    expect(
      screen.queryByText("LILONGWE UNIVERSITY OF AGRICULTURE AND NATURAL RESOURCES")
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Official opening wording.")).not.toBeInTheDocument();
    expect(screen.queryByText("Employee signature")).not.toBeInTheDocument();
    expect(screen.queryByText("LUANAR")).not.toBeInTheDocument();
  });
});