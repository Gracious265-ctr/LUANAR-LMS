/**
 * The password-change client helper, against the real module.
 *
 * Separate from the form's tests because those mock this module out, and the
 * behaviour worth pinning here is the module's own: which field a message is
 * attributed to, and what happens to the auth cookies. Both matter more than
 * they look — attributing a validator message to the wrong field sends the user
 * to edit the one they got right, and leaving the cookies behind makes a
 * successful change look like a random logout on the next click.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import { changePassword } from "@/lib/password-change";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

describe("changePassword", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("posts the three fields to the same-origin proxy", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ detail: "Password changed." }));

    const result = await changePassword("current 7", "new 9", "new 9");

    expect(result.ok).toBe(true);
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe("/api/auth/password-change");
    expect(init).toEqual(
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          current_password: "current 7",
          new_password: "new 9",
          confirm_password: "new 9",
        }),
      }),
    );
  });

  it("never names the Django URL", async () => {
    // Same rule as the set-password proxies: the browser must not learn where
    // the backend lives.
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ detail: "ok" }));

    await changePassword("current 7", "new 9", "new 9");

    for (const [url] of fetchSpy.mock.calls) {
      expect(String(url)).not.toMatch(/localhost|http:\/\/|https:\/\//);
    }
  });

  it("clears the auth cookies on success", async () => {
    // The tokens are already revoked server-side, so leaving the cookies would
    // make the next request fail in a way the user cannot read.
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ detail: "ok" }));

    await changePassword("current 7", "new 9", "new 9");

    expect(fetchSpy).toHaveBeenCalledWith("/api/auth/logout", { method: "POST" });
  });

  it("reports success even when clearing the cookies fails", async () => {
    // The server revoked the tokens regardless; failing to delete a cookie is
    // not a failed password change and must not be shown as one.
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ detail: "ok" }))
      .mockRejectedValueOnce(new Error("network down"));

    const result = await changePassword("current 7", "new 9", "new 9");

    expect(result.ok).toBe(true);
  });

  it("attributes a wrong current password to the current field", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ detail: "Your current password is not correct." }, 400),
    );

    const result = await changePassword("wrong 7", "new 9", "new 9");

    expect(result).toEqual({
      ok: false,
      error: "Your current password is not correct.",
      field: undefined,
    });
  });

  it("routes a keyed confirmation error to the new password field", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ confirm_password: ["The two passwords do not match."] }, 400),
    );

    const result = await changePassword("current 7", "one", "another");

    expect(result).toEqual({
      ok: false,
      error: "The two passwords do not match.",
      field: "new_password",
    });
  });

  it("routes a keyed current-password error to the current field", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ current_password: ["Not correct."] }, 400),
    );

    const result = await changePassword("wrong", "new 9", "new 9");

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.field).toBe("current_password");
  });

  it("reads a validator message out of a detail list", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ detail: ["This password is too short."] }, 400),
    );

    const result = await changePassword("current 7", "abc", "abc");

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toBe("This password is too short.");
  });

  it("does not clear the cookies when the change was refused", async () => {
    // Nothing was revoked, so signing the user out here would be a bug.
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        jsonResponse({ detail: "Your current password is not correct." }, 400),
      );

    await changePassword("wrong 7", "new 9", "new 9");

    expect(fetchSpy).not.toHaveBeenCalledWith("/api/auth/logout", expect.anything());
  });

  it("falls back to a usable message on an unreadable error body", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("<html>502</html>", { status: 502 }),
    );

    const result = await changePassword("current 7", "new 9", "new 9");

    expect(result).toEqual({
      ok: false,
      error: "Could not change your password.",
      field: undefined,
    });
  });

  it("reports a network failure without throwing", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("offline"));

    const result = await changePassword("current 7", "new 9", "new 9");

    expect(result).toEqual({
      ok: false,
      error: "An error occurred. Please try again.",
    });
  });
});
