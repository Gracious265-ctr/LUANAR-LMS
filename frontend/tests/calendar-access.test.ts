/**
 * The Calendar gate (refinement unit 07 §2).
 *
 * The backend is the authority — Django refuses every calendar write a
 * non-HR account attempts — but the launcher card and the page gate are
 * written twice, once in Python (`calendar_app.services.can_access_calendar`)
 * and once here. Unlike the HR sidebar, the launcher *does* hand superusers the
 * Calendar card, so the frontend gate must admit them too; the first version
 * checked `role === "hr"` alone and bounced a superuser to `/dashboard` the
 * moment they opened the card. These tests pin the arms that mistake dropped.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/headers", () => ({
  cookies: vi.fn(),
}));

vi.mock("next/navigation", async (importOriginal) => {
  const actual = await importOriginal<typeof import("next/navigation")>();
  return { ...actual, redirect: vi.fn() };
});

vi.mock("@/lib/auth", () => ({
  getCurrentUser: vi.fn(),
}));

import { redirect } from "next/navigation";

import { getCurrentUser } from "@/lib/auth";
import { canAccessCalendar, requireCalendarAccess } from "@/lib/financial-years";

function user(overrides: Record<string, unknown> = {}) {
  return {
    id: 3,
    email: "someone@luanar.mw",
    role: "employee",
    full_name: "Someone",
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("canAccessCalendar", () => {
  it("admits HR and the bootstrap administrator", () => {
    expect(canAccessCalendar(user({ role: "hr" }) as never)).toBe(true);
    expect(canAccessCalendar(user({ is_superuser: true }) as never)).toBe(true);
  });

  it("turns everyone else away", () => {
    expect(canAccessCalendar(user() as never)).toBe(false);
    expect(canAccessCalendar(user({ role: "approver" }) as never)).toBe(false);
    expect(canAccessCalendar(null)).toBe(false);
  });
});

describe("requireCalendarAccess", () => {
  it("sends a visitor with no session to the login page", async () => {
    vi.mocked(getCurrentUser).mockResolvedValue(null);

    await requireCalendarAccess();

    expect(vi.mocked(redirect).mock.calls[0]?.[0]).toBe("/login");
  });

  it("sends an ordinary employee back to their dashboard", async () => {
    vi.mocked(getCurrentUser).mockResolvedValue(user() as never);

    await requireCalendarAccess();

    expect(vi.mocked(redirect).mock.calls[0]?.[0]).toBe("/dashboard");
    expect(vi.mocked(redirect)).not.toHaveBeenCalledWith("/login");
  });

  it("lets a superuser through rather than bouncing the launcher card", async () => {
    const admin = user({ role: "employee", is_superuser: true }) as never;
    vi.mocked(getCurrentUser).mockResolvedValue(admin);

    await expect(requireCalendarAccess()).resolves.toBe(admin);
    expect(redirect).not.toHaveBeenCalled();
  });

  it("hands HR the user it resolved, so the page does not read it twice", async () => {
    const hr = user({ role: "hr" }) as never;
    vi.mocked(getCurrentUser).mockResolvedValue(hr);

    await expect(requireCalendarAccess()).resolves.toBe(hr);
    expect(redirect).not.toHaveBeenCalled();
  });
});
