import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DecisionDialog } from "@/components/approvals/decision-dialog";
import { makeBriefing, makeReview } from "@/lib/approvals/__fixtures__";
import { postDecision } from "@/lib/approvals/service";

vi.mock("@/lib/approvals/service", () => ({
  postDecision: vi.fn(),
}));

const mockedPostDecision = vi.mocked(postDecision);

function renderDialog(
  kind: "approve" | "reject",
  overrides: {
    onSubmitted?: (briefing: ReturnType<typeof makeBriefing>) => void;
    onReloadRequest?: () => void;
    onClose?: () => void;
  } = {}
) {
  const props = {
    kind,
    data: makeReview(),
    onClose: overrides.onClose ?? vi.fn(),
    onSubmitted: overrides.onSubmitted ?? vi.fn(),
    onReloadRequest: overrides.onReloadRequest ?? vi.fn(),
  };
  const utils = render(<DecisionDialog {...props} />);
  return { ...utils, props };
}

describe("DecisionDialog", () => {
  it("approve allows an empty trimmed comment and sends stage_version", async () => {
    const briefing = makeBriefing();
    mockedPostDecision.mockResolvedValue({ ok: true, data: briefing });
    const onSubmitted = vi.fn();
    renderDialog("approve", { onSubmitted });

    fireEvent.click(screen.getByRole("button", { name: /^Approved$/ }));

    await waitFor(() => expect(mockedPostDecision).toHaveBeenCalled());
    const payload = mockedPostDecision.mock.calls[0][1];
    expect(payload).toEqual({ action: "approve", comment: "", stage_version: 1 });
    expect(onSubmitted).toHaveBeenCalledWith(briefing);
  });

  it("reject disables the confirm button until a non-empty trimmed comment", async () => {
    mockedPostDecision.mockResolvedValue({ ok: true, data: makeBriefing({ status: "rejected" }) });
    renderDialog("reject");

    const confirm = screen.getByRole("button", { name: /^Rejected$/ });
    expect(confirm).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Reason (required)"), {
      target: { value: "   Missing documents   " },
    });

    expect(await screen.findByText("23 / 1000")).toBeInTheDocument();
    expect(confirm).toBeEnabled();

    fireEvent.click(confirm);

    await waitFor(() => expect(mockedPostDecision).toHaveBeenCalled());
    expect(mockedPostDecision.mock.calls[0][1]).toEqual({
      action: "reject",
      comment: "Missing documents",
      stage_version: 1,
    });
  });

  it("blocks a whitespace-only comment for reject", async () => {
    mockedPostDecision.mockResolvedValue({ ok: true, data: makeBriefing({ status: "rejected" }) });
    renderDialog("reject");

    fireEvent.change(screen.getByLabelText("Reason (required)"), {
      target: { value: "   " },
    });

    const confirm = screen.getByRole("button", { name: /^Rejected$/ });
    expect(confirm).toBeDisabled();
    expect(screen.getByText("3 / 1000")).toBeInTheDocument();
  });

  it("shows the reload banner on a 409 stage_changed conflict", async () => {
    mockedPostDecision.mockResolvedValue({
      ok: false,
      kind: "conflict",
      message: "This application has changed since you opened it.",
      reason: "stage_changed",
    });
    const onReloadRequest = vi.fn();
    renderDialog("approve", { onReloadRequest });

    fireEvent.click(screen.getByRole("button", { name: /^Approved$/ }));

    expect(
      await screen.findByText(
        "This application has changed since you opened it."
      )
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Reload" }));
    expect(onReloadRequest).toHaveBeenCalled();
  });

  it("shows a blocked message with no Reload when no approver remains", async () => {
    mockedPostDecision.mockResolvedValue({
      ok: false,
      kind: "blocked",
      message:
        "This application cannot be advanced: every remaining approval stage (Registrar) resolves to the applicant themself.",
      reason: "workflow_unavailable",
    });
    const onReloadRequest = vi.fn();
    renderDialog("approve", { onReloadRequest });

    fireEvent.click(screen.getByRole("button", { name: /^Approved$/ }));

    expect(
      await screen.findByText(/every remaining approval stage \(Registrar\)/)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Reloading will not help/)
    ).toBeInTheDocument();
    // A refresh cannot resolve it, so no Reload affordance is offered and the
    // decision cannot be retried.
    expect(screen.queryByRole("button", { name: "Reload" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Approved$/ })).toBeDisabled();
  });

  it("shows field errors for a 400 response", async () => {
    mockedPostDecision.mockResolvedValue({
      ok: false,
      kind: "validation",
      message: "The decision could not be submitted.",
      fields: { comment: "This field may not be blank." },
    });
    renderDialog("reject");

    fireEvent.change(screen.getByLabelText("Reason (required)"), {
      target: { value: "Reason here" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Rejected$/ }));

    expect(
      await screen.findByText("This field may not be blank.")
    ).toBeInTheDocument();
  });

  it("shows the next-stage label for a non-final approve", async () => {
    renderDialog("approve");
    expect(await screen.findByText("Next stage: Registrar.")).toBeInTheDocument();
  });

  it("shows the final-stage warning when the current stage is final", async () => {
    const data = makeReview();
    data.workflow.current_stage = {
      order: 4,
      role: "dvc",
      role_label: "DVC",
      is_final: true,
      next_role_label: null,
    };
    const props = {
      kind: "approve" as const,
      data,
      onClose: vi.fn(),
      onSubmitted: vi.fn(),
      onReloadRequest: vi.fn(),
    };
    render(<DecisionDialog {...props} />);
    expect(
      await screen.findByText(
        "This is the final approval stage. Approving will finalise this leave application."
      )
    ).toBeInTheDocument();
  });
});