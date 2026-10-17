/**
 * The Leave Plans browser proxies.
 *
 * Each route is a two-line pass-through, so the tests stay narrow: does it hit
 * the right Django path with the method/body/query intact, and does a refusal
 * arrive as a refusal? Cookie refresh is `apiFetch`'s job and is covered by
 * tests/api-fetch.test.ts, so it is mocked away here rather than re-pinned.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/headers", () => ({
  cookies: vi.fn(),
}));

import { cookies } from "next/headers";

import { GET as listGET, POST as listPOST } from "@/app/api/plans/route";
import {
  GET as detailGET,
  DELETE as detailDELETE,
} from "@/app/api/plans/[id]/route";
import { POST as applyPOST } from "@/app/api/plans/[id]/apply/route";
import { GET as teamGET } from "@/app/api/plans/team/route";
import { GET as scopeOptionsGET } from "@/app/api/plans/scope-options/route";

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

describe("Leave Plans proxies", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockCookies("an-access-token");
  });

  it("GET /api/plans forwards to the Django list endpoint", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ count: 0, results: [] }));

    await listGET();

    expect(fetchSpy).toHaveBeenCalledWith(
      `${DJANGO}/api/v1/plans/`,
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("POST /api/plans forwards the JSON body to Django", async () => {
    const body = { leave_type: 1, planned_start_date: "2026-11-02" };
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ id: "plan-1" }, 201));

    await listPOST(
      new Request("http://localhost:3000/api/plans/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    );

    expect(fetchSpy).toHaveBeenCalledWith(
      `${DJANGO}/api/v1/plans/`,
      expect.objectContaining({ method: "POST", body: JSON.stringify(body) }),
    );
  });

  it("GET /api/plans/{id} forwards to the id-scoped endpoint", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ id: "plan-7" }));

    await detailGET(new Request("http://localhost:3000/api/plans/plan-7/"), params("plan-7"));

    expect(fetchSpy).toHaveBeenCalledWith(
      `${DJANGO}/api/v1/plans/plan-7/`,
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("DELETE /api/plans/{id} forwards a DELETE and preserves a 204", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 204 }));

    const response = await detailDELETE(
      new Request("http://localhost:3000/api/plans/plan-7/", { method: "DELETE" }),
      params("plan-7"),
    );

    expect(fetchSpy).toHaveBeenCalledWith(
      `${DJANGO}/api/v1/plans/plan-7/`,
      expect.objectContaining({ method: "DELETE" }),
    );
    expect(response.status).toBe(204);
  });

  it("POST /api/plans/{id}/apply forwards to the apply action", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ application_id: "draft-1" }));

    await applyPOST(
      new Request("http://localhost:3000/api/plans/plan-7/apply/", { method: "POST" }),
      params("plan-7"),
    );

    expect(fetchSpy).toHaveBeenCalledWith(
      `${DJANGO}/api/v1/plans/plan-7/apply/`,
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("GET /api/plans/team carries the scope and month through as query params", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ results: [] }));

    await teamGET(
      new Request("http://localhost:3000/api/plans/team?scope=team:3&month=2026-11"),
    );

    expect(fetchSpy).toHaveBeenCalledWith(
      `${DJANGO}/api/v1/plans/team/?scope=team%3A3&month=2026-11`,
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("GET /api/plans/scope-options forwards to the scope endpoint", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse([]));

    await scopeOptionsGET();

    expect(fetchSpy).toHaveBeenCalledWith(
      `${DJANGO}/api/v1/plans/scope-options/`,
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("returns 401 when there is no session", async () => {
    mockCookies(undefined);
    const response = await listGET();
    expect(response.status).toBe(401);
  });
});
