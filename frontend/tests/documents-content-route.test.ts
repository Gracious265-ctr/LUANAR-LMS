import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GET } from "@/app/api/leave/leave-applications/[id]/documents/[docId]/content/route";

const cookiesMock = vi.fn();

vi.mock("next/headers", () => ({
  cookies: () => cookiesMock(),
}));

const upstreamFetch = vi.fn();

beforeEach(() => {
  cookiesMock.mockReset();
  upstreamFetch.mockReset();
  vi.stubGlobal("fetch", upstreamFetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const params = { id: "abc", docId: "doc-1" };

describe("document content proxy route", () => {
  it("streams bytes with a Bearer token replayed from the cookie", async () => {
    cookiesMock.mockResolvedValue({
      get: (name: string) =>
        name === "access_token" ? { value: "sekret" } : undefined,
    });
    upstreamFetch.mockResolvedValue(
      new Response("PDF-BYTES", {
        status: 200,
        headers: {
          "Content-Type": "application/pdf",
          "Content-Disposition": 'attachment; filename="cert.pdf"',
        },
      })
    );

    const res = await GET(new Request("http://x"), { params: Promise.resolve(params) });

    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toBe("application/pdf");
    expect(res.headers.get("content-disposition")).toContain("cert.pdf");
    expect(await res.text()).toBe("PDF-BYTES");

    const [url, init] = upstreamFetch.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/v1/leave-applications/abc/documents/doc-1/content/");
    expect((init as RequestInit).headers).toEqual({ Authorization: "Bearer sekret" });
  });

  it("makes an unauthenticated upstream call when no token cookie exists", async () => {
    cookiesMock.mockResolvedValue({ get: () => undefined });
    upstreamFetch.mockResolvedValue(new Response("ok", { status: 200 }));

    await GET(new Request("http://x"), { params: Promise.resolve(params) });

    expect(upstreamFetch.mock.calls[0][1]).toEqual({ headers: {} });
  });

  it("forwards a 404 upstream error with its status", async () => {
    cookiesMock.mockResolvedValue({ get: () => undefined });
    upstreamFetch.mockResolvedValue(
      new Response(JSON.stringify({ detail: "not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      })
    );

    const res = await GET(new Request("http://x"), { params: Promise.resolve(params) });

    expect(res.status).toBe(404);
    const body = JSON.parse((await res.text()) || "{}");
    expect(body.detail).toBe("not found");
  });
});