import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { NewApplicationClient } from "@/components/leave/NewApplicationClient";
import { getLeaveTypes } from "@/lib/services/leaveTypes";

const { pushMock, replaceMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  replaceMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/leave/new",
  useRouter: () => ({
    push: pushMock,
    replace: replaceMock,
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/services/leaveTypes", () => ({ getLeaveTypes: vi.fn() }));

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getLeaveTypes).mockResolvedValue([]);
});

describe("NewApplicationClient", () => {
  it("opens the compose dialog on its own route", () => {
    render(<NewApplicationClient />);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("New leave application")).toBeInTheDocument();
  });

  it("returns to the applications list when closed", async () => {
    render(<NewApplicationClient />);

    fireEvent.click(screen.getByRole("button", { name: /close/i }));

    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/leave"));
  });
});
