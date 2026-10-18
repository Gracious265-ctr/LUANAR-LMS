import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from "vitest";

import { AppLauncherGrid } from "@/components/launcher/app-launcher-grid";
import { getLauncherApps } from "@/lib/launcher";

vi.mock("@/lib/launcher", () => ({
  getLauncherApps: vi.fn(),
}));

const mockedGet = vi.mocked(getLauncherApps);

let errorSpy: MockInstance;

beforeEach(() => {
  vi.clearAllMocks();
  errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  const messages = errorSpy.mock.calls.map((call) => String(call[0]));
  errorSpy.mockRestore();
  // A card wrapped its block children in <p>, which React reports as invalid
  // nesting ("<div> cannot be a descendant of <p>"). It rendered, but caused a
  // hydration error, so guard against it rather than trusting the markup.
  expect(
    messages.filter((message) => /cannot be a descendant|cannot contain a nested/i.test(message))
  ).toEqual([]);
});

describe("AppLauncherGrid", () => {
  it("renders a card per app the backend returned", async () => {
    mockedGet.mockResolvedValue({
      apps: [
        { key: "leave", badge: null },
        { key: "approvals", badge: { count: 3, label: "pending", tone: "amber" } },
      ],
    });

    render(<AppLauncherGrid />);

    expect(
      await screen.findByRole("link", { name: /Leave Applications/ })
    ).toHaveAttribute("href", "/leave");
    expect(
      screen.getByRole("link", { name: /Approvals/ })
    ).toHaveAttribute("href", "/approvals");
  });

  it("shows the badge count and label when a module has one", async () => {
    mockedGet.mockResolvedValue({
      apps: [
        { key: "approvals", badge: { count: 3, label: "pending", tone: "amber" } },
      ],
    });

    render(<AppLauncherGrid />);

    expect(await screen.findByText(/3 pending/)).toBeInTheDocument();
  });

  it("renders no badge for an app whose badge is null", async () => {
    mockedGet.mockResolvedValue({ apps: [{ key: "leave", badge: null }] });

    render(<AppLauncherGrid />);

    await screen.findByRole("link", { name: /Leave Applications/ });
    expect(screen.queryByText(/pending/)).not.toBeInTheDocument();
  });

  it("drops keys it does not recognise in its own registry", async () => {
    mockedGet.mockResolvedValue({
      apps: [
        { key: "leave", badge: null },
        { key: "made-up-app", badge: null },
      ],
    });

    render(<AppLauncherGrid />);

    await screen.findByRole("link", { name: /Leave Applications/ });
    expect(screen.getAllByRole("link")).toHaveLength(1);
  });

  it("explains an empty result instead of rendering an empty grid", async () => {
    mockedGet.mockResolvedValue({ apps: [] });

    render(<AppLauncherGrid />);

    expect(
      await screen.findByText(/No apps available for your role/i)
    ).toBeInTheDocument();
  });

  it("falls back to the empty state when the request fails", async () => {
    mockedGet.mockRejectedValue(new Error("boom"));

    render(<AppLauncherGrid />);

    await waitFor(() =>
      expect(
        screen.getByText(/No apps available for your role/i)
      ).toBeInTheDocument()
    );
  });
});
