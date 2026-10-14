import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { format, parseISO } from "date-fns";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PlanForm } from "@/components/plans/plan-form";
import { selectOption } from "./helpers/select";
import { makeDraftDetail } from "@/lib/plans/__fixtures__";

/** October 2026 is the calendar's default month, so day lookups are stable. */
const TODAY = new Date(2026, 9, 5);

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh, replace: vi.fn(), prefetch: vi.fn() }),
}));

function dayButton(iso: string): HTMLElement {
  return within(screen.getByRole("grid")).getByRole("button", {
    name: format(parseISO(iso), "PPPP"),
  });
}

/**
 * Picks both ends of a range picker.
 *
 * The trigger's accessible name comes from the `Field` label rather than the
 * placeholder, because a `Field` label takes precedence over button content.
 */
function chooseRange(name: string | RegExp, from: string, to: string) {
  fireEvent.click(screen.getByRole("button", { name }));
  fireEvent.click(dayButton(from));
  fireEvent.click(dayButton(to));
}

function choosePeriod(from: string, to: string) {
  chooseRange("Period covered", from, to);
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("PlanForm", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(TODAY);
    push.mockClear();
    refresh.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  function renderForm() {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/leave/leave-types/")) {
          return Promise.resolve(
            jsonResponse([
              { id: 1, name: "Annual leave", code: "annual" },
              { id: 2, name: "Study leave", code: "study" },
            ])
          );
        }
        return Promise.resolve(jsonResponse(makeDraftDetail()));
      })
    );

    return render(<PlanForm />);
  }

  it("offers the leave types once they load", async () => {
    renderForm();

    const trigger = await screen.findByRole("combobox", {
      name: "Leave type (block 1)",
    });

    expect(trigger).toBeInTheDocument();
  });

  it("starts with one block and adds more on request", async () => {
    renderForm();
    await screen.findByRole("combobox", { name: "Leave type (block 1)" });

    expect(
      screen.queryByRole("combobox", { name: "Leave type (block 2)" })
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Add block/ }));

    expect(
      screen.getByRole("combobox", { name: "Leave type (block 2)" })
    ).toBeInTheDocument();
  });

  it("keeps one block when the last one is removed", async () => {
    renderForm();
    await screen.findByRole("combobox", { name: "Leave type (block 1)" });

    fireEvent.click(screen.getByRole("button", { name: "Remove block 1" }));

    // An empty plan cannot be submitted, so the row comes back rather than
    // leaving a form with nothing in it.
    expect(
      screen.getByRole("combobox", { name: "Leave type (block 1)" })
    ).toBeInTheDocument();
  });

  it("refuses to save without a period", async () => {
    renderForm();
    await screen.findByRole("combobox", { name: "Leave type (block 1)" });

    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));

    expect(
      await screen.findByText("Choose the period the plan covers.")
    ).toBeInTheDocument();
  });

  it("refuses to save a block that is missing its leave type", async () => {
    renderForm();
    await screen.findByRole("combobox", { name: "Leave type (block 1)" });

    choosePeriod("2026-10-01", "2026-10-30");
    chooseRange("Dates (block 1)", "2026-10-12", "2026-10-14");

    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));

    expect(
      await screen.findByText("Every block needs a leave type and a date range.")
    ).toBeInTheDocument();
  });

  it("saves a draft and moves to the new plan", async () => {
    renderForm();
    await screen.findByRole("combobox", { name: "Leave type (block 1)" });

    choosePeriod("2026-10-01", "2026-10-30");
    await selectOption(
      screen.getByRole("combobox", { name: "Leave type (block 1)" }),
      "Annual leave"
    );
    chooseRange("Dates (block 1)", "2026-10-12", "2026-10-14");

    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/dashboard/plans/plan-1"));

    const saveCall = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.find(
      ([url]) => url === "/api/plans/"
    );
    expect(saveCall?.[1]?.method).toBe("POST");
    expect(JSON.parse(String(saveCall?.[1]?.body))).toEqual({
      period_start: "2026-10-01",
      period_end: "2026-10-30",
      blocks: [
        {
          leave_type_id: 1,
          start_date: "2026-10-12",
          end_date: "2026-10-14",
        },
      ],
    });
  });

  it("sends one block per row it holds", async () => {
    renderForm();
    await screen.findByRole("combobox", { name: "Leave type (block 1)" });

    fireEvent.click(screen.getByRole("button", { name: /Add block/ }));

    choosePeriod("2026-10-01", "2026-10-30");
    await selectOption(
      screen.getByRole("combobox", { name: "Leave type (block 1)" }),
      "Annual leave"
    );
    chooseRange("Dates (block 1)", "2026-10-12", "2026-10-14");
    await selectOption(
      screen.getByRole("combobox", { name: "Leave type (block 2)" }),
      "Study leave"
    );
    chooseRange("Dates (block 2)", "2026-10-19", "2026-10-21");

    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));

    await waitFor(() => expect(push).toHaveBeenCalled());

    const saveCall = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.find(
      ([url]) => url === "/api/plans/"
    );
    expect(JSON.parse(String(saveCall?.[1]?.body)).blocks).toEqual([
      { leave_type_id: 1, start_date: "2026-10-12", end_date: "2026-10-14" },
      { leave_type_id: 2, start_date: "2026-10-19", end_date: "2026-10-21" },
    ]);
  });

  it("shows the reason the backend refused the save", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/leave/leave-types/")) {
          return Promise.resolve(
            jsonResponse([{ id: 1, name: "Annual leave", code: "annual" }])
          );
        }
        return Promise.resolve(
          jsonResponse({ detail: "Block overlaps another plan." }, 400)
        );
      })
    );
    render(<PlanForm />);
    await screen.findByRole("combobox", { name: "Leave type (block 1)" });

    choosePeriod("2026-10-01", "2026-10-30");
    await selectOption(
      screen.getByRole("combobox", { name: "Leave type (block 1)" }),
      "Annual leave"
    );
    chooseRange("Dates (block 1)", "2026-10-12", "2026-10-14");

    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));

    expect(
      await screen.findByText("Block overlaps another plan.")
    ).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });

  it("does not navigate when the save fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        String(input).includes("/api/leave/leave-types/")
          ? Promise.resolve(jsonResponse([]))
          : Promise.reject(new Error("down"))
      )
    );
    render(<PlanForm />);
    await screen.findByRole("combobox", { name: "Leave type (block 1)" });

    choosePeriod("2026-10-01", "2026-10-30");
    chooseRange("Dates (block 1)", "2026-10-12", "2026-10-14");

    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));

    await waitFor(() => expect(push).not.toHaveBeenCalled());
  });

  it("says so when the leave types cannot be loaded", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("down"))));
    render(<PlanForm />);

    expect(
      await screen.findByText(/Could not load leave types/)
    ).toBeInTheDocument();
  });

  it("says a draft is not routed anywhere until it is submitted", async () => {
    renderForm();
    await screen.findByRole("combobox", { name: "Leave type (block 1)" });

    expect(
      screen.getByText("A draft is not routed anywhere until you submit it.")
    ).toBeInTheDocument();
  });
});
