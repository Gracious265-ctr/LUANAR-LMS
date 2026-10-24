import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LeaveTypeForm } from "@/components/leave-config/LeaveTypeForm";
import { type LeaveType } from "@/lib/leave-config";
import {
  LeaveConfigRequestError,
  createLeaveType,
  deactivateLeaveType,
  listGrades,
  reactivateLeaveType,
  updateLeaveType,
} from "@/lib/leave-config-client";

import { selectOption } from "./helpers/select";

const { routerMock } = vi.hoisted(() => ({
  routerMock: {
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    prefetch: vi.fn(),
    refresh: vi.fn(),
  },
}));

vi.mock("next/navigation", async (importOriginal) => {
  const actual = await importOriginal<typeof import("next/navigation")>();
  return {
    ...actual,
    usePathname: () => "/leave-config",
    useRouter: () => routerMock,
  };
});

vi.mock("@/lib/leave-config-client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/leave-config-client")>();
  return {
    ...actual,
    createLeaveType: vi.fn(),
    updateLeaveType: vi.fn(),
    deactivateLeaveType: vi.fn(),
    reactivateLeaveType: vi.fn(),
    listGrades: vi.fn(),
  };
});

function leaveType(overrides: Partial<LeaveType> = {}): LeaveType {
  return {
    id: 7,
    name: "Study leave",
    code: "study",
    color: "purple",
    description: "Long study leave",
    branch_scope: "both",
    eligible_grades: ["A", "G"],
    eligible_gender: "any",
    requires_supporting_document: true,
    max_duration_days: 21,
    notice_days: 14,
    eligibility: "",
    eligibility_rules: [],
    consumes_annual_entitlement: false,
    plannable: true,
    requires_institutional_registrar_approval: false,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
    ...overrides,
  };
}

/** The create route passes nothing; the edit route passes the record. */
function renderForm(overrides: Partial<LeaveType> | undefined = undefined) {
  return render(<LeaveTypeForm leaveType={overrides && leaveType(overrides)} />);
}

function submit() {
  // Deliberately the form's own submit event rather than a click on the
  // button: jsdom enforces `required` on a click-driven submit, which would
  // stop the handler before the inline message this test is about.
  fireEvent.submit(screen.getByRole("button", { name: /create leave type|save/i }).closest("form")!);
}

function typeName(value: string) {
  fireEvent.change(screen.getByLabelText("Name"), { target: { value } });
}

function goToStep(name: string) {
  fireEvent.click(screen.getByRole("button", { name: name }));
}

async function goToEligibility() {
  // Already on Eligibility or past it (Rules)? Nothing to click.
  if (
    screen.queryByLabelText("Branch scope") ||
    screen.queryByLabelText("Maximum duration (days)")
  ) {
    return;
  }
  const name = screen.getByLabelText("Name") as HTMLInputElement;
  if (!name.value && !name.readOnly) {
    fireEvent.change(name, { target: { value: "Test Leave" } });
  }
  goToStep("Next");
  await waitFor(() =>
    expect(screen.queryByLabelText("Branch scope")).toBeTruthy()
  );
}

async function goToRules() {
  await goToEligibility();
  if (screen.queryByLabelText("Maximum duration (days)")) {
    return;
  }
  goToStep("Next");
  await waitFor(() =>
    expect(screen.queryByLabelText("Maximum duration (days)")).toBeTruthy()
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  routerMock.push.mockClear();
  routerMock.refresh.mockClear();
  vi.mocked(listGrades).mockResolvedValue([
    { id: "A", name: "Grade A" },
    { id: "G", name: "Grade G" },
  ]);
  vi.mocked(createLeaveType).mockResolvedValue(leaveType({ id: 9 }));
  vi.mocked(updateLeaveType).mockResolvedValue(leaveType());
  vi.mocked(deactivateLeaveType).mockResolvedValue(leaveType({ is_active: false }));
  vi.mocked(reactivateLeaveType).mockResolvedValue(leaveType({ is_active: true }));
});

describe("LeaveTypeForm — the five sections (spec 3.3)", () => {
  it("offers every section the spec lists and no entitlement field", async () => {
    renderForm();

    expect(screen.getAllByRole("heading", { name: "Basics" }).length).toBeGreaterThan(0);
    await goToRules();

    expect(screen.getByRole("heading", { name: "Planning" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Approval" })).toBeInTheDocument();

    // §1.3: the days-per-year number is not a property of a leave type, so no
    // control could be mistaken for one.
    expect(screen.queryByLabelText(/days per year/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/^entitlement/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/entitlement/i)).not.toBeInTheDocument();
  });

  it("pre-selects the defaults a new type starts from", async () => {
    renderForm();

    expect(screen.getByLabelText("Indigo")).not.toBeChecked();
    expect(screen.getByLabelText("Blue")).toBeChecked();
    await goToEligibility();
    expect(screen.getByLabelText("Branch scope")).toHaveTextContent("Both");
    expect(screen.getByLabelText("Eligible gender")).toHaveTextContent("Any");
    await goToRules();
    expect(screen.getByRole("checkbox", { name: /plannable/i })).toBeChecked();
    expect(
      screen.getByLabelText("Requires a supporting document")
    ).not.toBeChecked();
  });

  it("offers the directory's grades for eligibility, not a typed-in list", async () => {
    renderForm();
    await goToEligibility();

    expect(await screen.findByLabelText("Grade A")).toBeInTheDocument();
    expect(screen.getByLabelText("Grade G")).toBeInTheDocument();
    expect(screen.queryByLabelText("Grade Z")).not.toBeInTheDocument();
  });

  it("hides the registrar question for an Academic-scoped type", async () => {
    renderForm({ branch_scope: "administrative" });
    // Need to go to rules
    try {
      const nameInput = screen.getByLabelText("Name") as HTMLInputElement;
      if (!nameInput.value) fireEvent.change(nameInput, { target: { value: "Test Leave" } });
    } catch (e) {}
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(screen.getByLabelText("Branch scope")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(screen.getByLabelText("Maximum duration (days)")).toBeInTheDocument());
    expect(
      screen.getByRole("heading", { name: "Approval" })
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    await waitFor(() => expect(screen.getByLabelText("Branch scope")).toBeInTheDocument());
    await selectOption(
      screen.getByLabelText("Branch scope"),
      "Academic"
    );
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(screen.getByLabelText("Maximum duration (days)")).toBeInTheDocument());

    await waitFor(() =>
      expect(
        screen.queryByRole("heading", { name: "Approval" })
      ).not.toBeInTheDocument()
    );
    expect(
      screen.getByRole("heading", { name: "Planning" })
    ).toBeInTheDocument();
  });

  it("offers the registrar question again once the scope is not Academic", async () => {
    renderForm({ branch_scope: "academic" });
    try {
      const nameInput = screen.getByLabelText("Name") as HTMLInputElement;
      if (!nameInput.value) fireEvent.change(nameInput, { target: { value: "Test Leave" } });
    } catch (e) {}
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(screen.getByLabelText("Branch scope")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(screen.getByLabelText("Maximum duration (days)")).toBeInTheDocument());
    expect(
      screen.queryByRole("heading", { name: "Approval" })
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    await waitFor(() => expect(screen.getByLabelText("Branch scope")).toBeInTheDocument());
    await selectOption(screen.getByLabelText("Branch scope"), "Administrative");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(screen.getByLabelText("Maximum duration (days)")).toBeInTheDocument());

    expect(
      await screen.findByRole("heading", { name: "Approval" })
    ).toBeInTheDocument();
  });
});

describe("LeaveTypeForm — inline validation (spec 3.3)", () => {
  it("requires a name", async () => {
    renderForm();
    // Try to go to next without filling name
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Name is required.");
    expect(createLeaveType).not.toHaveBeenCalled();
  });

  it("rejects a negative maximum duration without leaving the page", async () => {
    renderForm();
    typeName("Study leave");
    await goToRules();
    fireEvent.change(screen.getByLabelText("Maximum duration (days)"), {
      target: { value: "-3" },
    });

    fireEvent.click(screen.getByRole("button", { name: /create leave type/i }));

    expect(
      screen.getByRole("alert")
    ).toHaveTextContent(
      "Maximum duration must be a whole number of at least 1 day."
    );
    expect(createLeaveType).not.toHaveBeenCalled();
  });

  it("rejects a negative notice period", async () => {
    renderForm();
    typeName("Study leave");
    await goToRules();
    fireEvent.change(screen.getByLabelText("Notice period (days)"), {
      target: { value: "-1" },
    });

    fireEvent.click(screen.getByRole("button", { name: /create leave type/i }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Notice period must be a whole number of days and cannot be negative."
    );
    expect(createLeaveType).not.toHaveBeenCalled();
  });

  it("clears a field's message as soon as the field is corrected", async () => {
    renderForm();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("alert")).toBeInTheDocument();

    typeName("Study leave");

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("LeaveTypeForm — saving", () => {
  it("creates a type and returns to the list", async () => {
    renderForm();
    typeName("  Study leave  ");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(screen.getByLabelText("Branch scope")).toBeInTheDocument());
    await screen.findByLabelText("Grade A");
    fireEvent.click(screen.getByLabelText("Grade A"));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(screen.getByLabelText("Notice period (days)")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("Notice period (days)"), {
      target: { value: "14" },
    });

    fireEvent.click(screen.getByRole("button", { name: /create leave type/i }));

    await waitFor(() => expect(createLeaveType).toHaveBeenCalledTimes(1));
    expect(vi.mocked(createLeaveType).mock.calls[0][0]).toMatchObject({
      name: "Study leave",
      notice_days: 14,
      color: "blue",
      branch_scope: "both",
      eligible_grades: ["A"],
      max_duration_days: null,
    });
    expect(routerMock.push).toHaveBeenCalledWith("/leave-config");
  });

  it("edits the record it was given", async () => {
    renderForm({});
    typeName("Sabbatical leave");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(screen.getByLabelText("Branch scope")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(screen.getByLabelText("Maximum duration (days)")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => expect(updateLeaveType).toHaveBeenCalledTimes(1));
    expect(vi.mocked(updateLeaveType).mock.calls[0][0]).toBe(7);
    expect(routerMock.push).toHaveBeenCalledWith("/leave-config");
  });

  it("shows a field error next to the field it belongs to", async () => {
    vi.mocked(createLeaveType).mockRejectedValue(
      new LeaveConfigRequestError("Validation failed", {
        name: ["A leave type with this name already exists."],
      })
    );
    renderForm();
    typeName("Annual leave");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(screen.getByLabelText("Branch scope")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(screen.getByLabelText("Maximum duration (days)")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /create leave type/i }));

    // The name field lives on Basics, so the form returns there and shows the
    // message beside it without the reader hunting for it.
    await waitFor(() => expect(screen.getByLabelText("Name")).toBeInTheDocument());
    expect(
      screen.getByText("A leave type with this name already exists.")
    ).toBeInTheDocument();
    // The message belongs to the name field, so the form-level banner stays
    // empty rather than repeating it.
    expect(screen.queryByText("Validation failed")).not.toBeInTheDocument();
    expect(routerMock.push).not.toHaveBeenCalled();
  });

  it("falls back to a banner when the complaint has no field", async () => {
    vi.mocked(createLeaveType).mockRejectedValue(
      new LeaveConfigRequestError("Validation failed", {
        non_field_errors: ["Only one annual leave type may exist."],
      })
    );
    renderForm();
    typeName("Annual leave two");
    await goToRules();

    fireEvent.click(screen.getByRole("button", { name: /create leave type/i }));

    expect(
      await screen.findByText("Only one annual leave type may exist.")
    ).toBeInTheDocument();
    expect(routerMock.push).not.toHaveBeenCalled();
  });
});

describe("LeaveTypeForm — the record's own state", () => {
  it("tells the reader an inactive type is retired instead of editing it", () => {
    renderForm({ is_active: false, eligible_grades: [] });

    expect(
      screen.getByText(/This leave type is inactive/i)
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Reactivate" })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Deactivate" })
    ).not.toBeInTheDocument();
  });

  it("offers Deactivate, not Delete, for a live type", () => {
    renderForm({});

    expect(
      screen.getByRole("button", { name: "Deactivate" })
    ).toBeInTheDocument();
    // §1.5: retired by deactivation, never by deletion.
    expect(
      screen.queryByRole("button", { name: /delete/i })
    ).not.toBeInTheDocument();
  });

  it("edits annual leave's rules while its identity stays fixed", async () => {
    renderForm({ name: "Annual leave", code: "annual" });

    // Its rules have no other home now that the Leave Rules screens are gone,
    // so this form is where HR changes them.
    await waitFor(() => expect(screen.getByLabelText("Name")).toBeInTheDocument());
    expect(screen.getByLabelText("Name")).toHaveValue("Annual leave");
    expect(screen.getByLabelText("Name")).toHaveAttribute("readonly");
    expect(screen.getByLabelText("Short code")).toHaveAttribute("readonly");
    await goToRules();

    fireEvent.change(screen.getByLabelText("Notice period (days)"), {
      target: { value: "21" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => expect(updateLeaveType).toHaveBeenCalledTimes(1));
    expect(vi.mocked(updateLeaveType).mock.calls[0][1]).toMatchObject({
      name: "Annual leave",
      code: "annual",
      notice_days: 21,
    });
  });

  it("says where the annual leave number comes from", () => {
    renderForm({ name: "Annual leave", code: "annual" });

    expect(
      screen.getByText(/created for you the first time you add an entitlement/i)
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "the entitlement" })
    ).toHaveAttribute("href", "/dashboard/hr-admin/entitlements");
  });

  it("offers no deactivate control for the annual type", () => {
    renderForm({ name: "Annual leave", code: "annual" });

    // The API refuses to retire it, so the control must not be dangled.
    expect(
      screen.queryByRole("button", { name: "Deactivate" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Reactivate" })
    ).not.toBeInTheDocument();
  });
});

describe("LeaveTypeForm — deactivation (spec 1.5 / 3.4)", () => {
  it("asks for confirmation and retires the type", async () => {
    renderForm({});

    fireEvent.click(screen.getByRole("button", { name: "Deactivate" }));

    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByRole("heading", {
        name: "Deactivate Study leave?",
      })
    ).toBeInTheDocument();
    expect(within(dialog).getByText(/Existing applications and plans/i)).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole("button", { name: "Deactivate" }));

    await waitFor(() =>
      expect(deactivateLeaveType).toHaveBeenCalledWith(7)
    );
    expect(routerMock.refresh).toHaveBeenCalled();
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    );
  });

  it("offers a way out of the confirmation", async () => {
    renderForm({});

    fireEvent.click(screen.getByRole("button", { name: "Deactivate" }));
    const dialog = await screen.findByRole("dialog");

    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));

    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    );
    expect(deactivateLeaveType).not.toHaveBeenCalled();
  });

  it("turns the same dialog into a reactivation for a retired type", async () => {
    renderForm({ is_active: false, eligible_grades: [] });

    fireEvent.click(screen.getByRole("button", { name: "Reactivate" }));

    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByRole("heading", { name: "Reactivate Study leave?" })
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText(/Employees will be able to select/i)
    ).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole("button", { name: "Reactivate" }));

    await waitFor(() => expect(reactivateLeaveType).toHaveBeenCalledWith(7));
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    );
  });

  it("keeps the confirmation open and explains itself if the write fails", async () => {
    vi.mocked(deactivateLeaveType).mockRejectedValue(
      new LeaveConfigRequestError("Nope", { detail: "Cannot deactivate." })
    );
    renderForm({});

    fireEvent.click(screen.getByRole("button", { name: "Deactivate" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Deactivate" }));

    expect(
      await within(dialog).findByText("Nope")
    ).toBeInTheDocument();
    expect(dialog).toBeInTheDocument();
    expect(routerMock.refresh).not.toHaveBeenCalled();
  });
});
