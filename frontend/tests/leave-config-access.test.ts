/**
 * The `/leave-config` gate (spec 4.5–4.6).
 *
 * The backend is the authority — Django refuses every write the screens
 * attempt — but the pages still decide who may see them at all, and the
 * launcher card and the page gate are written twice, once in Python and once
 * here. These two functions are the whole of the frontend half of that
 * decision, so they are pinned rather than left to be discovered by an HR
 * account clicking a card that bounces.
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
import {
  canAccessLeaveConfig,
  requireLeaveConfigAccess,
} from "@/lib/leave-config-server";

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

describe("canAccessLeaveConfig", () => {
  it("admits HR and the bootstrap administrator", () => {
    expect(canAccessLeaveConfig(user({ role: "hr" }) as never)).toBe(true);
    expect(
      canAccessLeaveConfig(user({ is_superuser: true }) as never)
    ).toBe(true);
  });

  it("turns everyone else away", () => {
    expect(canAccessLeaveConfig(user() as never)).toBe(false);
    expect(canAccessLeaveConfig(user({ role: "approver" }) as never)).toBe(false);
    expect(canAccessLeaveConfig(null)).toBe(false);
  });
});

describe("requireLeaveConfigAccess", () => {
  it("sends a visitor with no session to the login page", async () => {
    vi.mocked(getCurrentUser).mockResolvedValue(null);

    await requireLeaveConfigAccess();

    // The real `redirect` throws, so production stops here; the mocked one
    // returns, which is why the gate below is allowed to run too.
    expect(vi.mocked(redirect).mock.calls[0]?.[0]).toBe("/login");
  });

  it("sends an ordinary employee back to their dashboard", async () => {
    vi.mocked(getCurrentUser).mockResolvedValue(user() as never);

    await requireLeaveConfigAccess();

    expect(vi.mocked(redirect).mock.calls[0]?.[0]).toBe("/dashboard");
    expect(vi.mocked(redirect)).not.toHaveBeenCalledWith("/login");
  });

  it("hands HR the user it resolved, so the page does not read it twice", async () => {
    const hr = user({ role: "hr" }) as never;
    vi.mocked(getCurrentUser).mockResolvedValue(hr);

    await expect(requireLeaveConfigAccess()).resolves.toBe(hr);
    expect(redirect).not.toHaveBeenCalled();
  });
});
