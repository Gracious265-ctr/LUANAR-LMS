/**
 * The in-app notification browser proxies.
 *
 * Four two-line pass-throughs, so the tests stay narrow: does each route hit
 * the right Django path with the method and query intact, and does a refusal
 * arrive as a refusal? Cookie refresh is `apiFetch`'s job (tests/api-fetch) and
 * is mocked away here rather than re-pinned.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/headers", () => ({
  cookies: vi.fn(),
}));

import { cookies } from "next/headers";

import { GET as listGET } from "@/app/api/notifications/route";
import { GET as countGET } from "@/app/api/notifications/unread-count/route";
import { POST as markAllPOST } from "@/app/api/notifications/mark-all-read/route";
import { POST as markReadPOST } from "@/app/api/notifications/[id]/mark-read/route";

const DJANGO = process.env.DJANGO_API_URL || "http://localhost:8000";

function mockCookies(access: string | undefined) {
  vi.mocked(cookies).mockResolvedValue({
    get: (name: string) =>
      name === "access_token" && access ? { name, value: access } : undefined,
  } as never);
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

const params = (id: string) => ({ params: Promise.resolve({ id }) });

describe("notification proxies", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockCookies("an-access-token");
  });

  it("GET /api/notifications forwards to the Django list endpoint", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse([]));

    await listGET(new Request("http://localhost:3000/api/notifications/"));

    expect(fetchSpy).toHaveBeenCalledWith(
      `${DJANGO}/api/v1/notifications/`,
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("GET /api/notifications carries unread_only through as a query param", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse([]));

    await listGET(
      new Request("http://localhost:3000/api/notifications/?unread_only=true"),
    );

    expect(fetchSpy).toHaveBeenCalledWith(
      `${DJANGO}/api/v1/notifications/?unread_only=true`,
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("GET /api/notifications/unread-count forwards to the badge endpoint", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ count: 4 }));

    await countGET();

    expect(fetchSpy).toHaveBeenCalledWith(
      `${DJANGO}/api/v1/notifications/unread-count/`,
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("POST /api/notifications/mark-all-read forwards the POST", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 204 }));

    const response = await markAllPOST();

    expect(fetchSpy).toHaveBeenCalledWith(
      `${DJANGO}/api/v1/notifications/mark-all-read/`,
      expect.objectContaining({ method: "POST" }),
    );
    expect(response.status).toBe(204);
  });

  it("POST /api/notifications/{id}/mark-read forwards the id-scoped action", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 204 }));

    const response = await markReadPOST(
      new Request("http://localhost:3000/api/notifications/n-7/mark-read/", {
        method: "POST",
      }),
      params("n-7"),
    );

    expect(fetchSpy).toHaveBeenCalledWith(
      `${DJANGO}/api/v1/notifications/n-7/mark-read/`,
      expect.objectContaining({ method: "POST" }),
    );
    expect(response.status).toBe(204);
  });

  it("returns 401 when there is no session", async () => {
    mockCookies(undefined);
    const response = await countGET();
    expect(response.status).toBe(401);
  });
});
