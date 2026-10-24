/**
 * The navbar notification bell (refinement unit 08 §3.7).
 *
 * The service module is mocked so each test pins one behaviour: badge
 * presence/capping, the popover's empty state, and the one-click row action
 * that both follows the link and marks the row read. The 30-second poll is
 * covered with fake timers rather than real ones.
 */

import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NotificationBell } from "@/components/notifications/NotificationBell";
import {
  getUnreadCount,
  listNotifications,
  markAllRead,
  markRead,
} from "@/lib/notifications/service";
import type { Notification } from "@/lib/notifications/types";

const { routerMock } = vi.hoisted(() => ({
  routerMock: { push: vi.fn() },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
  usePathname: () => "/dashboard",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/notifications/service", () => ({
  getUnreadCount: vi.fn(),
  listNotifications: vi.fn(),
  markRead: vi.fn(),
  markAllRead: vi.fn(),
}));

const UNREAD: Notification = {
  id: "n-1",
  event_type: "application.approved",
  message: "Your Annual Leave application was approved",
  link: "/applications/abc123",
  is_read: false,
  created_at: "2026-10-21T07:00:00Z",
};

const READ: Notification = {
  ...UNREAD,
  id: "n-2",
  message: "Your Study Leave application was rejected",
  is_read: true,
};

function openBell() {
  fireEvent.click(screen.getByRole("button", { name: "Notifications" }));
}

describe("NotificationBell", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getUnreadCount.mockResolvedValue(0);
    listNotifications.mockResolvedValue([]);
    markRead.mockResolvedValue(undefined);
    markAllRead.mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders no badge at all when the unread count is 0", async () => {
    render(<NotificationBell />);

    expect(
      await screen.findByRole("button", { name: "Notifications" })
    ).toBeInTheDocument();
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("shows the exact count while it is between 1 and 9", async () => {
    getUnreadCount.mockResolvedValue(3);
    render(<NotificationBell />);

    expect(await screen.findByText("3")).toBeInTheDocument();
    expect(screen.queryByText("9+")).not.toBeInTheDocument();
  });

  it("caps the badge at 9+ once the count exceeds 9", async () => {
    getUnreadCount.mockResolvedValue(12);
    render(<NotificationBell />);

    expect(await screen.findByText("9+")).toBeInTheDocument();
    expect(screen.queryByText("12")).not.toBeInTheDocument();
  });

  it("re-polls the unread count every 30 seconds", async () => {
    vi.useFakeTimers();
    getUnreadCount.mockResolvedValue(3);
    render(<NotificationBell />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(getUnreadCount).toHaveBeenCalledTimes(1);
    expect(screen.getByText("3")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(getUnreadCount).toHaveBeenCalledTimes(2);
  });

  it("renders the empty state when there are no notifications", async () => {
    render(<NotificationBell />);
    openBell();

    expect(
      await screen.findByText("You're all caught up")
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Mark all read" })).toBeNull();
  });

  it("marks a read-only list without offering any read actions", async () => {
    listNotifications.mockResolvedValue([{ ...UNREAD, is_read: true }]);
    render(<NotificationBell />);
    openBell();

    expect(await screen.findByText(UNREAD.message)).toBeInTheDocument();
    // Nothing is unread, so there is no header and no "Mark all read".
    expect(screen.queryByRole("heading", { name: "Notifications" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Mark all read" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Mark as read/ })).toBeNull();
  });

  it("clicking a row marks it read and navigates in the same action", async () => {
    listNotifications.mockResolvedValue([UNREAD]);
    render(<NotificationBell />);
    openBell();

    fireEvent.click(await screen.findByText(UNREAD.message));

    expect(markRead).toHaveBeenCalledWith(UNREAD.id);
    expect(routerMock.push).toHaveBeenCalledWith(UNREAD.link);
    // Following the link closes the popover.
    await waitFor(() =>
      expect(screen.queryByText(UNREAD.message)).not.toBeInTheDocument()
    );
  });

  it("the inline tick marks a row read without navigating or closing", async () => {
    listNotifications.mockResolvedValue([UNREAD]);
    render(<NotificationBell />);
    openBell();

    fireEvent.click(
      await screen.findByRole("button", {
        name: `Mark as read: ${UNREAD.message}`,
      })
    );

    expect(markRead).toHaveBeenCalledWith(UNREAD.id);
    expect(routerMock.push).not.toHaveBeenCalled();
    expect(screen.getByText(UNREAD.message)).toBeInTheDocument();
    // The row is read now, so its affordance disappears in place.
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /Mark as read/ })).toBeNull()
    );
  });

  it('"Mark all read" clears every row and the badge without reopening', async () => {
    getUnreadCount.mockResolvedValueOnce(2).mockResolvedValue(0);
    listNotifications.mockResolvedValue([UNREAD, READ]);
    render(<NotificationBell />);
    openBell();

    expect(
      await screen.findByRole("button", { name: "Mark all read" })
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Mark all read" }));

    expect(markAllRead).toHaveBeenCalled();
    // Every row updates in place and the header retires with the last unread.
    expect(screen.queryByRole("button", { name: /Mark as read/ })).toBeNull();
    expect(screen.getByText(UNREAD.message)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Mark all read" })
    ).toBeNull();
    // The badge refetches immediately rather than waiting for the next poll.
    await waitFor(() => expect(screen.queryByText("2")).not.toBeInTheDocument());
  });
});
