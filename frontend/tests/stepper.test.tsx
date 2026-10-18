import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Stepper, type Step } from "@/components/ui/Stepper";
import {
  chainFromPlanStages,
  chainFromTracking,
  chainFromWorkflow,
  stepsFromCancellation,
} from "@/lib/chain-steps";
import { formatDateTime } from "@/lib/format";
import type { ApprovalStage } from "@/lib/approvals/types";
import type { CancellationStage } from "@/lib/cancellations/types";
import type { PlanStage } from "@/lib/plans/types";
import type { TrackingResponse } from "@/lib/tracking/types";

function makeStep(overrides: Partial<Step> = {}): Step {
  return {
    id: "step-1",
    label: "HOD",
    status: "completed",
    actor: { id: "jane", name: "Jane Phiri" },
    timestamp: "2026-09-22T08:00:00Z",
    ...overrides,
  };
}

describe("Stepper", () => {
  it("renders sequences of varying length without dropping any step", () => {
    const short = render(
      <Stepper
        steps={[
          makeStep(),
          makeStep({ id: "step-2", status: "current", timestamp: null }),
        ]}
      />
    );
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    short.unmount();

    render(
      <Stepper
        steps={[
          makeStep(),
          makeStep({ id: "step-2", status: "current", timestamp: null }),
          makeStep({ id: "step-3", status: "pending", timestamp: null }),
          makeStep({ id: "step-4", status: "pending", timestamp: null }),
          makeStep({ id: "step-5", status: "pending", timestamp: null }),
          makeStep({ id: "step-6", status: "pending", timestamp: null }),
        ]}
      />
    );
    expect(screen.getAllByRole("listitem")).toHaveLength(6);
  });

  it("marks exactly one current step with aria-current=step and data-state per node", () => {
    render(
      <Stepper
        steps={[
          makeStep(),
          makeStep({ id: "step-2", status: "current", timestamp: null }),
          makeStep({ id: "step-3", status: "pending", timestamp: null }),
        ]}
      />
    );

    expect(document.querySelectorAll('[aria-current="step"]')).toHaveLength(1);
    expect(document.querySelectorAll('[data-state="completed"]')).toHaveLength(1);
    expect(document.querySelectorAll('[data-state="current"]')).toHaveLength(1);
    expect(document.querySelectorAll('[data-state="pending"]')).toHaveLength(1);
  });

  it("renders all six statuses in visually distinct nodes", () => {
    const statuses = [
      "completed",
      "current",
      "pending",
      "skipped",
      "blocked",
      "error",
    ] as const;
    render(
      <Stepper
        showAvatars={false}
        steps={statuses.map((status, index) => ({
          id: `step-${index}`,
          label: status,
          status,
        }))}
      />
    );

    for (const status of statuses) {
      expect(document.querySelector(`[data-state="${status}"]`)).toBeInTheDocument();
    }
    // Brand fill for completed, dashed outline for skipped, red family for
    // blocked/error — no new colours introduced.
    expect(document.querySelector(".bg-brand-primary")).toBeInTheDocument();
    expect(document.querySelector(".border-dashed")).toBeInTheDocument();
    expect(document.querySelectorAll(".bg-status-rejected-subtle")).toHaveLength(2);
    // The rejection outcome uses the X icon, distinct from a blocker.
    expect(document.querySelector(".lucide-x")).toBeInTheDocument();
  });

  it("shows a blocked step's reason and an error step's detail", () => {
    render(
      <Stepper
        steps={[
          makeStep({
            id: "blocked",
            label: "Audit",
            status: "blocked",
            actor: null,
            sublabel: "No approver assigned",
          }),
          makeStep({
            id: "error",
            label: "HOD",
            status: "error",
            sublabel: "Rejected",
            detail: "Peak teaching period",
          }),
        ]}
      />
    );

    expect(screen.getByText("No approver assigned")).toBeInTheDocument();
    expect(screen.getByText("Rejected")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /HOD details/i }));
    expect(screen.getByText("Peak teaching period")).toBeInTheDocument();
  });

  it("keeps a skipped stage visible with its explanatory sublabel", () => {
    render(
      <Stepper
        steps={[
          makeStep({
            id: "skipped",
            status: "skipped",
            actor: null,
            sublabel: "Applicant cannot approve their own application",
          }),
          makeStep({ id: "step-2", status: "current", timestamp: null }),
        ]}
      />
    );

    expect(
      screen.getByText("Applicant cannot approve their own application")
    ).toBeInTheDocument();
    expect(document.querySelector('[data-state="skipped"]')).toBeInTheDocument();
  });

  it("renders the acting badge next to the actor's name", () => {
    render(
      <Stepper
        steps={[
          makeStep({
            id: "acting",
            status: "current",
            timestamp: null,
            isActing: true,
          }),
        ]}
      />
    );

    expect(screen.getByText("Jane Phiri")).toBeInTheDocument();
    expect(screen.getByText("Acting")).toBeInTheDocument();
  });

  it("switches orientation with breakpoints in one DOM tree", () => {
    const { rerender } = render(
      <Stepper
        steps={[makeStep(), makeStep({ id: "step-2", status: "current", timestamp: null })]}
      />
    );

    const autoList = screen.getByRole("list");
    expect(autoList.className).toContain("flex-col");
    expect(autoList.className).toContain("md:flex-row");
    const first = document.querySelector("li");
    const spans = Array.from(first?.querySelectorAll("span") ?? []);
    expect(spans.some((span) => span.className.includes("md:hidden"))).toBe(true);
    expect(
      spans.some(
        (span) =>
          span.className.includes("md:block") && span.className.includes("hidden")
      )
    ).toBe(true);

    rerender(
      <Stepper
        orientation="horizontal"
        steps={[makeStep(), makeStep({ id: "step-2", status: "current", timestamp: null })]}
      />
    );
    expect(screen.getByRole("list").className).toContain("flex-row");
    expect(screen.getByRole("list").className).not.toContain("md:flex-row");

    rerender(
      <Stepper
        orientation="vertical"
        steps={[makeStep(), makeStep({ id: "step-2", status: "current", timestamp: null })]}
      />
    );
    expect(screen.getByRole("list").className).toContain("flex-col");
    expect(screen.getByRole("list").className).not.toContain("md:flex-row");
  });

  it("renders compact size without the sublabel, actor line or timestamp", () => {
    render(
      <Stepper
        size="sm"
        steps={[
          makeStep({
            sublabel: "Assigned 21 Sep 2026, 11:12",
            timestamp: "2026-09-22T08:00:00Z",
          }),
        ]}
      />
    );

    expect(screen.getByText("HOD")).toBeInTheDocument();
    expect(screen.queryByText("Assigned 21 Sep 2026, 11:12")).not.toBeInTheDocument();
    expect(
      screen.queryByText(formatDateTime("2026-09-22T08:00:00Z"))
    ).not.toBeInTheDocument();
  });

  it("uses status nodes instead of avatars when showAvatars is false but keeps the actor name", () => {
    render(
      <Stepper showAvatars={false} steps={[makeStep()]} />
    );

    expect(screen.queryByText("JP")).not.toBeInTheDocument();
    expect(screen.getByText("Jane Phiri")).toBeInTheDocument();
    expect(document.querySelector(".bg-brand-primary")).toBeInTheDocument();
  });

  it("respects prefers-reduced-motion for the current pulse", () => {
    render(
      <Stepper
        steps={[makeStep({ id: "current", status: "current", timestamp: null })]}
      />
    );

    const pulse = document.querySelector(".animate-pulse");
    expect(pulse).toBeInTheDocument();
    expect(pulse?.className).toContain("motion-reduce:animate-none");
  });

  it("expands and collapses the detail accordion in place", () => {
    render(
      <Stepper
        steps={[
          makeStep({ detail: "Verified. Forwarded." }),
          makeStep({ id: "step-2", status: "current", timestamp: null }),
        ]}
      />
    );

    const toggle = screen.getByRole("button", { name: /HOD details/i });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Verified. Forwarded.")).not.toBeInTheDocument();

    fireEvent.click(toggle);
    expect(screen.getByText("Verified. Forwarded.")).toBeInTheDocument();
    expect(toggle).toHaveAttribute("aria-expanded", "true");

    fireEvent.click(toggle);
    expect(screen.queryByText("Verified. Forwarded.")).not.toBeInTheDocument();
  });
});

describe("chain adapters", () => {
  it("maps Unit 15 tracking stages onto steps, classifying error and blocked", () => {
    const data = {
      stages: [
        {
          order: 1,
          role: "supervisor",
          role_label: "Supervisor",
          state: "approved",
          approver: {
            name: "A B",
            designation: "Boss",
            is_delegate: false,
            on_behalf_of: null,
          },
          assigned_at: "2026-09-21T09:12:00Z",
          decided_at: "2026-09-22T10:00:00Z",
          comment: "ok",
          skip_reason: null,
        },
        {
          order: 2,
          role: "hod",
          role_label: "HOD",
          state: "rejected",
          approver: {
            name: "C D",
            designation: "Lecturer",
            is_delegate: true,
            on_behalf_of: "Dr. X",
          },
          assigned_at: "2026-09-22T10:00:00Z",
          decided_at: "2026-09-23T10:00:00Z",
          comment: "Peak teaching period",
          skip_reason: null,
        },
        {
          order: 3,
          role: "registrar",
          role_label: "Registrar",
          state: "awaiting",
          approver: null,
          assigned_at: null,
          decided_at: null,
          comment: null,
          skip_reason: null,
        },
        {
          order: 4,
          role: "dvc",
          role_label: "DVC",
          state: "upcoming",
          approver: null,
          assigned_at: null,
          decided_at: null,
          comment: null,
          skip_reason: null,
        },
        {
          order: 5,
          role: "audit",
          role_label: "Audit",
          state: "skipped",
          approver: null,
          assigned_at: null,
          decided_at: null,
          comment: null,
          skip_reason: "Applicant cannot approve their own application",
        },
      ],
    } as unknown as TrackingResponse;

    const steps = chainFromTracking(data);

    expect(steps.map((step) => step.status)).toEqual([
      "completed",
      "error",
      "blocked",
      "pending",
      "skipped",
    ]);
    expect(steps[0].actor).toEqual({ id: "A B", name: "A B" });
    expect(steps[0].sublabel).toContain("Boss");
    expect(steps[1].detail).toBe("Peak teaching period");
    expect(steps[1].sublabel).toContain("Rejected");
    expect(steps[1].isActing).toBe(true);
    expect(steps[2].sublabel).toBe("No approver assigned");
    expect(steps[4].sublabel).toBe(
      "Applicant cannot approve their own application"
    );
  });

  it("closes a correction-required tracking stage as an error with the reason", () => {
    const data = {
      stages: [
        {
          order: 1,
          role: "registrar",
          role_label: "Registrar",
          state: "returned",
          approver: {
            name: "C D",
            designation: "Registrar",
            is_delegate: false,
            on_behalf_of: null,
          },
          assigned_at: "2026-09-21T09:12:00Z",
          decided_at: "2026-09-23T10:00:00Z",
          comment: "Upload the missing file",
          skip_reason: null,
        },
      ],
    } as unknown as TrackingResponse;

    const [step] = chainFromTracking(data);
    expect(step.status).toBe("error");
    expect(step.sublabel).toContain("Correction required");
    expect(step.detail).toBe("Upload the missing file");
  });

  it("maps Unit 16 workflow stages onto steps", () => {
    const stages: ApprovalStage[] = [
      {
        order: 1,
        role: "supervisor",
        role_label: "Supervisor",
        status: "approved",
        decision_version: 1,
        assigned_approver: "A B",
        assigned_at: "2026-09-21T09:12:00Z",
        decided_at: "2026-09-22T10:00:00Z",
        comment: "ok",
        skip_reason: null,
      },
      {
        order: 2,
        role: "hod",
        role_label: "HOD",
        status: "pending",
        decision_version: 1,
        assigned_approver: "Jane Phiri",
        assigned_at: "2026-09-22T10:00:00Z",
        decided_at: null,
        comment: null,
        skip_reason: null,
      },
      {
        order: 3,
        role: "registrar",
        role_label: "Registrar",
        status: "correction_requested",
        decision_version: 1,
        assigned_approver: "C D",
        assigned_at: "2026-09-21T09:12:00Z",
        decided_at: "2026-09-23T10:00:00Z",
        comment: "Upload the missing file",
        skip_reason: null,
      },
      {
        order: 4,
        role: "dvc",
        role_label: "DVC",
        status: "waiting",
        decision_version: 0,
        assigned_approver: "",
        assigned_at: null,
        decided_at: null,
        comment: null,
        skip_reason: null,
      },
      {
        order: 5,
        role: "audit",
        role_label: "Audit",
        status: "skipped",
        decision_version: 0,
        assigned_approver: "E F",
        assigned_at: null,
        decided_at: null,
        comment: null,
        skip_reason: "Self approval",
      },
      {
        order: 6,
        role: "vice",
        role_label: "Vice Chancellor",
        status: "rejected",
        decision_version: 1,
        assigned_approver: "G H",
        assigned_at: "2026-09-21T09:12:00Z",
        decided_at: "2026-09-24T10:00:00Z",
        comment: "No",
        skip_reason: null,
      },
    ];

    const steps = chainFromWorkflow(stages);

    expect(steps.map((step) => step.status)).toEqual([
      "completed",
      "current",
      "error",
      "pending",
      "skipped",
      "error",
    ]);
    expect(steps[2].sublabel).toBe("Correction required");
    expect(steps[2].detail).toBe("Upload the missing file");
    expect(steps[4].sublabel).toBe("Self approval");
    expect(steps[5].sublabel).toBe("Rejected");
  });

  it("maps plan stages onto steps", () => {
    const stages: PlanStage[] = [
      {
        id: "s1",
        stage_order: 1,
        role: "supervisor",
        role_label: "Supervisor",
        role_ref_id: null,
        section_ref_id: null,
        history_scope: null,
        assigned_approver_id: 7,
        approver_name: "Jane Phiri",
        eligible_approver_ids: [],
        eligible_approvers: [],
        is_claimed: true,
        status: "approved",
        status_label: "Approved",
        is_final: true,
        decision_version: 1,
      },
      {
        id: "s2",
        stage_order: 2,
        role: "hod",
        role_label: "HOD",
        role_ref_id: null,
        section_ref_id: null,
        history_scope: null,
        assigned_approver_id: null,
        approver_name: "",
        eligible_approver_ids: [],
        eligible_approvers: [],
        is_claimed: false,
        status: "pending",
        status_label: "Pending",
        is_final: false,
        decision_version: 0,
      },
    ];

    const steps = chainFromPlanStages(stages);
    expect(steps.map((step) => step.status)).toEqual(["completed", "blocked"]);
    expect(steps[1].sublabel).toBe("No approver assigned");
  });

  it("maps cancellation stages onto a shortened chain", () => {
    const stages: CancellationStage[] = [
      {
        id: "c1",
        order: 1,
        role: "supervisor",
        role_label: "Supervisor",
        status: "approved",
        approver_name: "Jane Phiri",
        decided_at: "2026-09-24T10:00:00Z",
        comment: "Fine by me",
      },
      {
        id: "c2",
        order: 2,
        role: "hod",
        role_label: "HOD",
        status: "pending",
        approver_name: "C D",
        decided_at: null,
        comment: null,
      },
      {
        id: "c3",
        order: 3,
        role: "registrar",
        role_label: "Registrar",
        status: "waiting",
        approver_name: "",
        decided_at: null,
        comment: null,
      },
    ];

    const steps = stepsFromCancellation(stages);
    expect(steps.map((step) => step.status)).toEqual([
      "completed",
      "current",
      "pending",
    ]);
    expect(steps[0].actor).toEqual({ id: "Jane Phiri", name: "Jane Phiri" });
    expect(steps[0].detail).toBe("Fine by me");
    expect(steps[2].actor).toBeNull();
  });
});
