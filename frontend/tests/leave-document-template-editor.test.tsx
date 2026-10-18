import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { LeaveDocumentTemplateEditor } from "@/components/hr/leave-document-template-editor";
import type { LeaveDocumentTemplate } from "@/lib/leave-document-template";

import { selectOption } from "./helpers/select";

let user: ReturnType<typeof userEvent.setup>;

const { routerMock, searchParamsRef, pathnameRef } = vi.hoisted(() => ({
  routerMock: { push: vi.fn(), replace: vi.fn(), back: vi.fn(), refresh: vi.fn() },
  searchParamsRef: { current: new URLSearchParams() },
  pathnameRef: { current: "/hr-admin/leave-document-template" },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
  usePathname: () => pathnameRef.current,
  useSearchParams: () => searchParamsRef.current,
}));

vi.mock("@/lib/leave-document-template-client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/leave-document-template-client")>();
  return {
    ...actual,
    updateLeaveDocumentTemplate: vi.fn(),
  };
});

import { updateLeaveDocumentTemplate } from "@/lib/leave-document-template-client";

const availableFields = [
  { key: "reference", label: "Reference", sample: "LV-2026-000123" },
  { key: "employee_name", label: "Employee", sample: "Jane Employee" },
  { key: "employee_grade", label: "Grade", sample: "G" },
  { key: "designation", label: "Designation", sample: "Lecturer" },
  { key: "team", label: "Team", sample: "Agronomy Team" },
  { key: "leave_type", label: "Leave type", sample: "Annual leave" },
  { key: "start_date", label: "Start date", sample: "2026-10-05" },
  { key: "end_date", label: "End date", sample: "2026-10-23" },
  { key: "working_days", label: "Working days", sample: "15" },
  { key: "request_reason", label: "Reason", sample: "Personal leave" },
];

const template: LeaveDocumentTemplate = {
  title: "APPROVED LEAVE",
  header: "LILONGWE UNIVERSITY OF AGRICULTURE AND NATURAL RESOURCES",
  intro: "Official opening wording.",
  fields: [
    { key: "employee_name", label: "Employee" },
    { key: "reference", label: "Reference" },
  ],
  closing: "Official closing wording.",
  signature_areas: [{ label: "Employee signature" }, { label: "For: Registrar" }],
  footer: "LUANAR",
  available_fields: availableFields,
  updated_at: "2026-09-17T12:00:00Z",
};

describe("LeaveDocumentTemplateEditor", () => {
  beforeEach(() => {
    vi.mocked(updateLeaveDocumentTemplate).mockResolvedValue({ ...template });
    searchParamsRef.current = new URLSearchParams();
    user = userEvent.setup();
  });

  it("renders the saved configuration", () => {
    render(<LeaveDocumentTemplateEditor template={template} />);

    expect(screen.getByLabelText("Document title")).toHaveValue("APPROVED LEAVE");
    expect(screen.getByLabelText("Edit label: employee_name")).toHaveValue(
      "Employee"
    );
    expect(screen.getByLabelText("Edit label: reference")).toHaveValue(
      "Reference"
    );
    expect(screen.getByLabelText("Signature area 1 label")).toHaveValue(
      "Employee signature"
    );
    expect(screen.getByLabelText("Signature area 2 label")).toHaveValue(
      "For: Registrar"
    );
  });

  it("updates a field label in the form and the preview", () => {
    searchParamsRef.current = new URLSearchParams("preview=1");
    render(<LeaveDocumentTemplateEditor template={template} />);

    fireEvent.change(screen.getByLabelText("Edit label: employee_name"), {
      target: { value: "Employee Name" },
    });

    const preview = screen.getByLabelText("Document template preview");
    const previewRows = within(preview).getAllByRole("row");
    expect(previewRows[0].textContent).toContain("Employee Name");
    expect(previewRows[0].textContent).toContain("Jane Employee");
  });

  it("adds an unused catalog field in order", async () => {
    render(<LeaveDocumentTemplateEditor template={template} />);

    await selectOption(
      screen.getByLabelText("Add data field"),
      "End date",
      { user }
    );
    fireEvent.click(screen.getByLabelText("Add selected field"));

    const labelInputs = [
      screen.getByLabelText("Edit label: employee_name"),
      screen.getByLabelText("Edit label: reference"),
      screen.getByLabelText("Edit label: end_date"),
    ];
    expect(labelInputs).toHaveLength(3);
    expect(screen.getByLabelText("Edit label: end_date")).toHaveValue("End date");
  });

  it("does not offer already-used catalog fields for adding", () => {
    render(<LeaveDocumentTemplateEditor template={template} />);

    const select = screen.getByLabelText("Add data field");
    const options = Array.from(select.querySelectorAll("option")).map(
      (option) => option.textContent
    );
    expect(options).not.toContain("Employee");
    expect(options).not.toContain("Reference");
  });

  it("removes a field and keeps at least one", () => {
    render(<LeaveDocumentTemplateEditor template={template} />);

    fireEvent.click(screen.getByLabelText("Remove reference"));
    expect(
      screen.queryByLabelText("Edit label: reference")
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("Edit label: employee_name")).toHaveValue(
      "Employee"
    );
  });

  it("disables removing the last remaining field", () => {
    const single: LeaveDocumentTemplate = {
      ...template,
      fields: [{ key: "employee_name", label: "Employee" }],
    };
    render(<LeaveDocumentTemplateEditor template={single} />);

    expect(
      screen.getByLabelText("Remove employee_name")
    ).toBeDisabled();
  });

  it("reorders fields via the move buttons", () => {
    searchParamsRef.current = new URLSearchParams("preview=1");
    render(<LeaveDocumentTemplateEditor template={template} />);

    fireEvent.click(screen.getByLabelText("Move reference up"));

    const preview = screen.getByLabelText("Document template preview");
    const previewRows = within(preview).getAllByRole("row");
    expect(previewRows[0].textContent).toContain("Reference");
    expect(previewRows[0].textContent).toContain("LV-2026-000123");
    expect(previewRows[1].textContent).toContain("Employee");
  });

  it("adds and removes a signature area", () => {
    render(<LeaveDocumentTemplateEditor template={template} />);

    fireEvent.click(screen.getByRole("button", { name: "Add signature" }));
    expect(screen.getByLabelText("Signature area 3 label")).toHaveValue(
      "Signature"
    );

    fireEvent.click(screen.getByLabelText("Remove signature 3"));
    expect(
      screen.queryByLabelText("Signature area 3 label")
    ).not.toBeInTheDocument();
  });

  it("saves the current template shape through the client lib", () => {
    render(<LeaveDocumentTemplateEditor template={template} />);

    fireEvent.change(screen.getByLabelText("Document title"), {
      target: { value: "APPROVED LEAVE CERTIFICATE" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save template" }));

    expect(updateLeaveDocumentTemplate).toHaveBeenCalledWith({
      title: "APPROVED LEAVE CERTIFICATE",
      header: template.header,
      intro: template.intro,
      fields: template.fields,
      closing: template.closing,
      signature_areas: template.signature_areas,
      footer: template.footer,
    });
  });

  it("shows a saved notice after a successful save", async () => {
    render(<LeaveDocumentTemplateEditor template={template} />);

    fireEvent.click(screen.getByRole("button", { name: "Save template" }));

    expect(
      await screen.findByText("Template saved.")
    ).toBeInTheDocument();
  });

  it("renders the backend error message on a failed save", async () => {
    vi.mocked(updateLeaveDocumentTemplate).mockRejectedValue(
      new Error("fields: At least one data field is required.")
    );
    render(<LeaveDocumentTemplateEditor template={template} />);

    fireEvent.click(screen.getByRole("button", { name: "Save template" }));

    expect(
      await screen.findByText("fields: At least one data field is required.")
    ).toBeInTheDocument();
  });

  it("keeps the preview out of the page until it is asked for", () => {
    render(<LeaveDocumentTemplateEditor template={template} />);

    expect(
      screen.queryByLabelText("Document template preview")
    ).not.toBeInTheDocument();
  });

  it("opens the preview overlay from the button", () => {
    render(<LeaveDocumentTemplateEditor template={template} />);

    fireEvent.click(screen.getByRole("button", { name: /preview/i }));

    expect(routerMock.push).toHaveBeenCalledWith(
      "/hr-admin/leave-document-template?preview=1"
    );
  });

  it("shows the preview in a dialog once the URL asks for it", () => {
    searchParamsRef.current = new URLSearchParams("preview=1");
    render(<LeaveDocumentTemplateEditor template={template} />);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(
      screen.getByLabelText("Document template preview")
    ).toBeInTheDocument();
  });

  it("carries unsaved edits into the preview overlay", () => {
    searchParamsRef.current = new URLSearchParams("preview=1");
    render(<LeaveDocumentTemplateEditor template={template} />);

    fireEvent.change(screen.getByLabelText("Document title"), {
      target: { value: "DRAFT CERTIFICATE" },
    });

    expect(screen.getByLabelText("Document template preview")).toHaveTextContent(
      "DRAFT CERTIFICATE"
    );
  });

  it("steps the preview closed", () => {
    searchParamsRef.current = new URLSearchParams("preview=1");
    render(<LeaveDocumentTemplateEditor template={template} />);

    fireEvent.click(screen.getByRole("button", { name: "Close" }));

    // The lone JSDOM history entry takes close's replace fallback; either way
    // the point is that it did not `push` the user off the page.
    expect(routerMock.replace).toHaveBeenCalledWith(
      "/hr-admin/leave-document-template"
    );
    expect(routerMock.push).not.toHaveBeenCalled();
  });
});