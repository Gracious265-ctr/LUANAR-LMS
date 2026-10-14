import { beforeEach, describe, expect, it, vi } from "vitest";

import { POST as confirm } from "@/app/api/auth/password-set/confirm/route";
import { POST as request } from "@/app/api/auth/password-set/request/route";
import { GET as validate } from "@/app/api/auth/password-set/validate/route";

/**
 * The proxies are the only place the browser would learn the Django URL, and the
 * only place the token crosses into a body. These assertions are about that
 * boundary: what is forwarded, what comes back, and that a Django refusal is
 * passed through rather than flattened into a success.
 *
 * The host is read from the environment the same way the routes read it, so the
 * suite does not care whether one is configured.
 */

const DJANGO = process.env.DJANGO_API_URL || "http://localhost:8000";

function jsonRequest(body: unknown) {
  return new Request("http://localhost:3000/api/auth/password-set", {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("password-set proxy routes", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("forwards a link request to the anonymous endpoint", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ detail: "On its way." }));

    const response = await request(jsonRequest({ email: "someone@luanar.ac.mw" }));

    expect(fetchMock).toHaveBeenCalledWith(
      `${DJANGO}/api/v1/auth/password-set/request/`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ email: "someone@luanar.ac.mw" }),
      })
    );
    await expect(response.json()).resolves.toEqual({ detail: "On its way." });
  });

  it("passes a refusal through instead of pretending it worked", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ detail: "Enter a valid email address." }, 400)
    );

    const response = await request(jsonRequest({ email: "nope" }));

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({
      detail: "Enter a valid email address.",
    });
  });

  it("url-encodes the token when validating a link", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ valid: true }));

    const response = await validate(
      new Request(
        "http://localhost:3000/api/auth/password-set/validate?token=a%20b%26c"
      )
    );

    expect(fetchMock).toHaveBeenCalledWith(
      `${DJANGO}/api/v1/auth/password-set/validate/?token=a%20b%26c`,
      expect.objectContaining({ cache: "no-store" })
    );
    await expect(response.json()).resolves.toEqual({ valid: true });
  });

  it("forwards the token and the new password to confirm", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ detail: "Password set." }));

    const response = await confirm(
      jsonRequest({ token: "abc123", password: "a good long password" })
    );

    expect(fetchMock).toHaveBeenCalledWith(
      `${DJANGO}/api/v1/auth/password-set/confirm/`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ token: "abc123", password: "a good long password" }),
      })
    );
    expect(response.status).toBe(200);
  });

  it("does not invent a valid link when Django says no", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ valid: false }));

    const response = await validate(
      new Request("http://localhost:3000/api/auth/password-set/validate?token=dead")
    );

    await expect(response.json()).resolves.toEqual({ valid: false });
  });
});
