import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SetupHub } from "@/components/hr/setup/SetupHub";
import { Toaster } from "@/components/ui/toast";
import type { ApplyResult, SetupStatus } from "@/lib/setup";
import {
  applyDefaults,
  previewDefaults,
  rolloverFinancialYear,
} from "@/lib/setup-client";

const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh }),
}));

vi.mock("@/lib/setup-client", () => ({
  applyDefaults: vi.fn(),
  previewDefaults: vi.fn(),
  rolloverFinancialYear: vi.fn(),
}));

const EMPTY_RESULT: ApplyResult = {
  created: {},
  skipped: {},
  total_created: 0,
  dry_run: false,
};

function makeStatus(overrides: Partial<SetupStatus["steps"]> = {}): SetupStatus {
  const steps = {
    financial_year: { done: false, count: 0 },
    leave_types: { done: false, count: 0 },
    entitlements: { done: false, count: 0 },
    roles: { done: false, count: 0 },
    teams: { done: false, count: 0 },
    ...overrides,
  };
  return {
    steps,
    complete: Object.values(steps).every((step) => step.done),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("SetupHub", () => {
  it("lists the setup spine in order with a progress count", () => {
    render(<SetupHub status={makeStatus()} />);

    expect(screen.getByRole("heading", { name: "Get started" })).toBeInTheDocument();
    expect(screen.getByText("0 of 5 done")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open a financial year/ })).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Build a team and its approval chain/ })
    ).toBeInTheDocument();
  });

  it("reports completion from live data", () => {
    const status = makeStatus({
      financial_year: { done: true, count: 1 },
      leave_types: { done: true, count: 4 },
      entitlements: { done: true, count: 3 },
      roles: { done: true, count: 6 },
      teams: { done: true, count: 1 },
    });

    render(<SetupHub status={status} />);

    expect(screen.getByRole("heading", { name: "You're set up" })).toBeInTheDocument();
    expect(screen.getByText("5 of 5 done")).toBeInTheDocument();
  });

  it("previews the defaults, showing exactly what would be created", async () => {
    vi.mocked(previewDefaults).mockResolvedValue({
      created: { financial_year: 1, entitlements: 3, roles: 6 },
      skipped: { leave_types: 4 },
      total_created: 10,
      dry_run: true,
    });

    render(<SetupHub status={makeStatus()} />);
    fireEvent.click(
      screen.getByRole("button", { name: "Apply default configuration" })
    );

    expect(await screen.findByText(/This will create:/)).toBeInTheDocument();
    expect(screen.getByText("6 Approver roles")).toBeInTheDocument();
    expect(screen.getByText("3 Entitlement bands")).toBeInTheDocument();
    expect(screen.getByText("1 Financial year")).toBeInTheDocument();
  });

  it("applies the defaults, toasts, and refreshes the page", async () => {
    vi.mocked(previewDefaults).mockResolvedValue({
      created: { roles: 6 },
      skipped: {},
      total_created: 6,
      dry_run: true,
    });
    vi.mocked(applyDefaults).mockResolvedValue({
      created: { roles: 6 },
      skipped: {},
      total_created: 6,
      dry_run: false,
    });

    render(
      <>
        <SetupHub status={makeStatus()} />
        <Toaster />
      </>
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Apply default configuration" })
    );
    fireEvent.click(await screen.findByRole("button", { name: "Apply" }));

    await waitFor(() => expect(applyDefaults).toHaveBeenCalledTimes(1));
    expect(refresh).toHaveBeenCalled();
    expect(
      screen.getByText("Default configuration applied.")
    ).toBeInTheDocument();
  });

  it("says there is nothing to do when everything is present", async () => {
    vi.mocked(previewDefaults).mockResolvedValue({
      ...EMPTY_RESULT,
      dry_run: true,
    });

    render(<SetupHub status={makeStatus()} />);
    fireEvent.click(
      screen.getByRole("button", { name: "Apply default configuration" })
    );

    expect(
      await screen.findByText(/Everything is already configured/)
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Apply" })
    ).not.toBeInTheDocument();
  });

  it("surfaces a preview failure instead of an empty list", async () => {
    vi.mocked(previewDefaults).mockRejectedValue(
      new Error("Unable to reach the server.")
    );

    render(<SetupHub status={makeStatus()} />);
    fireEvent.click(
      screen.getByRole("button", { name: "Apply default configuration" })
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unable to reach the server."
    );
  });

  it("offers a year rollover only once a financial year exists", () => {
    render(<SetupHub status={makeStatus()} />);
    expect(
      screen.queryByRole("button", { name: "Start a new financial year" })
    ).not.toBeInTheDocument();

    render(
      <SetupHub
        status={makeStatus({ financial_year: { done: true, count: 1 } })}
      />
    );
    expect(
      screen.getByRole("button", { name: "Start a new financial year" })
    ).toBeInTheDocument();
  });

  it("opens the next financial year, toasts, and refreshes", async () => {
    vi.mocked(rolloverFinancialYear).mockResolvedValue({
      created: { financial_year: 1, leave_rules: 4 },
      skipped: {},
      total_created: 5,
      dry_run: false,
    });

    render(
      <>
        <SetupHub
          status={makeStatus({ financial_year: { done: true, count: 1 } })}
        />
        <Toaster />
      </>
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Start a new financial year" })
    );
    fireEvent.click(await screen.findByRole("button", { name: "Open new year" }));

    await waitFor(() => expect(rolloverFinancialYear).toHaveBeenCalledTimes(1));
    expect(refresh).toHaveBeenCalled();
    expect(screen.getByText("New financial year opened.")).toBeInTheDocument();
  });
});
