import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  fetchApprovalDetail,
  fetchApprovalsList,
  fetchCapabilities,
  fetchDocumentDownload,
  submitDecision,
} from "@/lib/approvals/service";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

function okResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("approvals service", () => {
  it("fetchCapabilities GETs the capabilities endpoint", async () => {
    fetchMock.mockResolvedValue(okResponse({ is_approver: true, pending_count: 2 }));

    const result = await fetchCapabilities();

    expect(result).toEqual({ is_approver: true, pending_count: 2 });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/approvals/capabilities/");
    expect(init).toMatchObject({ credentials: "include" });
  });

  it("fetchApprovalsList sends tab, q, page and page_size when set", async () => {
    fetchMock.mockResolvedValue(okResponse({ count: 0, next: null, previous: null, results: [] }));

    await fetchApprovalsList({ tab: "decided", q: "miriam", page: 2, pageSize: 20 });

    const url = new URL(fetchMock.mock.calls[0][0] as string);
    expect(url.pathname).toBe("/api/approvals/");
    expect(url.searchParams.get("tab")).toBe("decided");
    expect(url.searchParams.get("q")).toBe("miriam");
    expect(url.searchParams.get("page")).toBe("2");
    expect(url.searchParams.get("page_size")).toBe("20");
  });

  it("fetchApprovalsList omits defaults", async () => {
    fetchMock.mockResolvedValue(okResponse({ count: 0, next: null, previous: null, results: [] }));

    await fetchApprovalsList({});

    const url = new URL(fetchMock.mock.calls[0][0] as string);
    expect(url.searchParams.toString()).toBe("");
  });

  it("fetchApprovalDetail encodes the id in the path", async () => {
    fetchMock.mockResolvedValue(okResponse({ id: "aa1" }));

    await fetchApprovalDetail("aa/1");

    expect(fetchMock.mock.calls[0][0]).toContain("/api/approvals/aa%2F1/");
  });

  it("submitDecision posts JSON decision body", async () => {
    fetchMock.mockResolvedValue(okResponse({ id: "aa1" }));

    await submitDecision("aa1", {
      action: "approve",
      comment: "ok",
      stage_version: 3,
    });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/approvals/aa1/decision/");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      action: "approve",
      comment: "ok",
      stage_version: 3,
    });
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe(
      "application/json"
    );
  });

  it("throws ApiError with status and payload on failure", async () => {
    fetchMock.mockResolvedValue(
      okResponse({ detail: "Stage has changed." }, 409)
    );

    await expect(
      submitDecision("aa1", { action: "approve", comment: "", stage_version: 2 })
    ).rejects.toMatchObject({ status: 409 });

    await expect(fetchCapabilities).rejects.toBeInstanceOf(ApiError);
  });

  it("fetchDocumentDownload hits the download-url endpoint", async () => {
    fetchMock.mockResolvedValue(okResponse({ url: "https://cdn.example.test/file" }));

    const result = await fetchDocumentDownload("aa1", "d1");

    expect(result.url).toBe("https://cdn.example.test/file");
    expect(fetchMock.mock.calls[0][0]).toContain(
      "/api/approvals/aa1/documents/d1/download-url/"
    );
  });
});