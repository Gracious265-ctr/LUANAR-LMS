/**
 * The Leave Configuration browser proxies (spec 4.4).
 *
 * Narrow by design: each route is a pass-through, so what matters is that it
 * hits the right Django path with the method, body and query intact, that a
 * non-integer id never reaches Django, and that a missing session is a 401.
 * Cookie refresh is `apiFetch`'s job and is covered by tests/api-fetch.test.ts.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

vi.mock("next/headers", () => ({
  cookies: vi.fn(),
}));

import { cookies } from "next/headers";

import { GET as listGET, POST as listPOST } from "@/app/api/leave-config/types/route";
import {
  GET as detailGET,
  PATCH as detailPATCH,
} from "@/app/api/leave-config/types/[id]/route";
import { POST as deactivatePOST } from "@/app/api/leave-config/types/[id]/deactivate/route";
import { POST as reactivatePOST } from "@/app/api/leave-config/types/[id]/reactivate/route";
import { GET as gradesGET } from "@/app/api/leave-config/grades/route";

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

describe("Leave Configuration proxies", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockCookies("an-access-token");
  });

  it("GET /api/leave-config/types forwards to the Django list endpoint", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse([]));

    await listGET(new NextRequest("http://localhost:3000/api/leave-config/types"));

    expect(fetchSpy).toHaveBeenCalledWith(
      `${DJANGO}/api/v1/leave-config/types/`,
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("forwards include_inactive, and omits it when it is not asked for", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse([]));

    await listGET(
      new NextRequest(
        "http://localhost:3000/api/leave-config/types?include_inactive=true"
      )
    );
    expect(fetchSpy).toHaveBeenLastCalledWith(
      `${DJANGO}/api/v1/leave-config/types/?include_inactive=true`,
      expect.objectContaining({ method: "GET" }),
    );

    // The default view is active-only, so the query is dropped rather than
    // sent as false: every other module's dropdown reads this endpoint and
    // must not have to remember to filter.
    await listGET(
      new NextRequest("http://localhost:3000/api/leave-config/types?include_inactive=false")
    );
    expect(fetchSpy).toHaveBeenLastCalledWith(
      `${DJANGO}/api/v1/leave-config/types/`,
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("POST /api/leave-config/types forwards the JSON body to Django", async () => {
    const body = { name: "Study leave", notice_days: 14 };
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ id: 9 }, 201));

    await listPOST(
      new Request("http://localhost:3000/api/leave-config/types/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    );

    expect(fetchSpy).toHaveBeenCalledWith(
      `${DJANGO}/api/v1/leave-config/types/`,
      expect.objectContaining({ method: "POST", body: JSON.stringify(body) }),
    );
  });

  it("GET and PATCH the id-scoped endpoint", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ id: 7 }));

    await detailGET(
      new Request("http://localhost:3000/api/leave-config/types/7"),
      params("7"),
    );
    expect(fetchSpy).toHaveBeenLastCalledWith(
      `${DJANGO}/api/v1/leave-config/types/7/`,
      expect.objectContaining({ method: "GET" }),
    );

    await detailPATCH(
      new Request("http://localhost:3000/api/leave-config/types/7", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plannable: false }),
      }),
      params("7"),
    );
    expect(fetchSpy).toHaveBeenLastCalledWith(
      `${DJANGO}/api/v1/leave-config/types/7/`,
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ plannable: false }) }),
    );
  });

  it.each(["new", "../", "7a", "annual"])(
    "refuses %s as an id without troubling Django",
    async (id) => {
      const fetchSpy = vi.spyOn(globalThis, "fetch");

      const response = await detailGET(
        new Request(`http://localhost:3000/api/leave-config/types/${id}`),
        params(id),
      );

      expect(response.status).toBe(404);
      expect(fetchSpy).not.toHaveBeenCalled();
    },
  );

  it("POST /deactivate and /reactivate each hit their own action", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ id: 7, is_active: false }));

    await deactivatePOST(
      new Request("http://localhost:3000/api/leave-config/types/7/deactivate/", {
        method: "POST",
      }),
      params("7"),
    );
    expect(fetchSpy).toHaveBeenLastCalledWith(
      `${DJANGO}/api/v1/leave-config/types/7/deactivate/`,
      expect.objectContaining({ method: "POST" }),
    );

    await reactivatePOST(
      new Request("http://localhost:3000/api/leave-config/types/7/reactivate/", {
        method: "POST",
      }),
      params("7"),
    );
    expect(fetchSpy).toHaveBeenLastCalledWith(
      `${DJANGO}/api/v1/leave-config/types/7/reactivate/`,
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("GET /api/leave-config/grades forwards to the grade options", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse([{ id: "A", name: "Grade A" }]));

    await gradesGET();

    expect(fetchSpy).toHaveBeenCalledWith(
      `${DJANGO}/api/v1/leave-config/grades/`,
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("returns 401 when there is no session", async () => {
    mockCookies(undefined);
    const response = await listGET(
      new NextRequest("http://localhost:3000/api/leave-config/types")
    );
    expect(response.status).toBe(401);
  });
});
