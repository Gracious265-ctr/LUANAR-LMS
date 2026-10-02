import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LeaveRuleForm } from "@/components/hr/leave-rule-form";
import type { LeaveRule, LeaveType } from "@/lib/leave-rules";

const leaveTypes: LeaveType[] = [
  { id: 1, name: "Annual leave", code: "annual" },
  { id: 2, name: "Maternity leave", code: "maternity" },
  { id: 3, name: "Paternity leave", code: "paternity" },
];

const rule: LeaveRule = {
  id: 5,
  leave_type: 2,
  leave_type_code: "maternity",
  leave_type_name: "Maternity leave",
  max_duration_days: 90,
  eligibility: "Female employees",
  min_notice_days: 5,
  requires_supporting_document: true,
  consumes_annual_entitlement: false,
  effective_from: "2026-01-01",
};

describe("LeaveRuleForm", () => {
  it("renders rule fields for a new rule", () => {
    render(<LeaveRuleForm leaveTypes={leaveTypes} />);

    expect(screen.getByLabelText("Leave type")).toBeInTheDocument();
    expect(screen.getByLabelText("Maximum duration (days)")).toBeInTheDocument();
    expect(screen.getByLabelText("Minimum notice (days)")).toBeInTheDocument();
    expect(screen.getByLabelText("Effective from")).toBeInTheDocument();
    expect(screen.getByLabelText("Eligibility")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create rule" })).toBeInTheDocument();
  });

  it("offers every leave type in the dropdown", () => {
    render(<LeaveRuleForm leaveTypes={leaveTypes} />);

    const select = screen.getByLabelText("Leave type");
    const options = Array.from(
      select.querySelectorAll("option")
    ).map((option) => option.textContent);
    expect(options).toContain("Annual leave");
    expect(options).toContain("Maternity leave");
    expect(options).toContain("Paternity leave");
  });

  it("prefills values when editing an existing rule", () => {
    render(<LeaveRuleForm leaveRule={rule} leaveTypes={leaveTypes} />);

    expect(screen.getByLabelText("Maximum duration (days)")).toHaveValue(90);
    expect(screen.getByLabelText("Minimum notice (days)")).toHaveValue(5);
    expect(screen.getByLabelText("Effective from")).toHaveValue("2026-01-01");
    expect(screen.getByLabelText("Eligibility")).toHaveValue("Female employees");
    expect(screen.getByLabelText("Leave type")).toHaveValue("2");
    expect(
      screen.getByLabelText("Requires a supporting document")
    ).toBeChecked();
    expect(
      screen.getByLabelText("Consumes annual leave entitlement")
    ).not.toBeChecked();
    expect(screen.getByRole("button", { name: "Save changes" })).toBeInTheDocument();
  });

  it("provides a cancel link back to the leave rules index", () => {
    render(<LeaveRuleForm leaveTypes={leaveTypes} />);

    const cancel = screen.getByRole("link", { name: "Cancel" });
    expect(cancel.getAttribute("href")).toBe(
      "/dashboard/hr-admin/leave-rules"
    );
  });

  describe("inline leave type creation", () => {
    beforeEach(() => {
      vi.stubGlobal("fetch", vi.fn());
    });

    afterEach(() => {
      vi.unstubAllGlobals();
    });

    it("creates a leave type inline and selects it", async () => {
      const created: LeaveType = {
        id: 4,
        name: "Study leave",
        code: "study",
      };
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify(created), {
          status: 201,
          headers: { "Content-Type": "application/json" },
        })
      );

      render(<LeaveRuleForm leaveTypes={leaveTypes} />);

      fireEvent.click(
        screen.getByRole("button", { name: "Create leave type" })
      );
      fireEvent.change(screen.getByLabelText("New leave type name"), {
        target: { value: "Study leave" },
      });
      fireEvent.click(
        screen.getByRole("button", { name: "Save leave type" })
      );

      await waitFor(() =>
        expect(vi.mocked(fetch)).toHaveBeenCalledWith(
          "/api/hr/leave-types",
          expect.objectContaining({ method: "POST" })
        )
      );
      await waitFor(() =>
        expect(screen.getByLabelText("Leave type")).toHaveValue("4")
      );
      expect(
        Array.from(
          (screen.getByLabelText("Leave type") as HTMLSelectElement).options
        ).map((option) => option.textContent)
      ).toEqual([
        "Choose a leave type…",
        "Annual leave",
        "Maternity leave",
        "Paternity leave",
        "Study leave",
      ]);
    });

    it("shows the server's reason when a leave type cannot be created", async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(
          JSON.stringify({ detail: "A leave type with this name already exists." }),
          {
            status: 400,
            headers: { "Content-Type": "application/json" },
          }
        )
      );

      render(<LeaveRuleForm leaveTypes={leaveTypes} />);

      fireEvent.click(
        screen.getByRole("button", { name: "Create leave type" })
      );
      fireEvent.change(screen.getByLabelText("New leave type name"), {
        target: { value: "Annual leave" },
      });
      fireEvent.click(
        screen.getByRole("button", { name: "Save leave type" })
      );

      await waitFor(() =>
        expect(
          screen.getByText("A leave type with this name already exists.")
        ).toBeInTheDocument()
      );
    });
  });
});