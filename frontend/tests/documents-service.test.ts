import { beforeEach, describe, expect, it, vi } from "vitest";

import { formatFileSize } from "@/lib/documents/config";
import {
  DocumentRequestError,
  documentContentUrl,
  getDocumentConfig,
  getDocumentHistory,
  listDocuments,
  removeDocument,
  replaceDocument,
  uploadDocument,
} from "@/lib/documents/service";

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

const DOC = {
  id: "doc-1",
  file_path: "leave-documents/abc/doc-1/cert.pdf",
  file_url: "",
  file_name: "cert.pdf",
  file_size: 2048,
  content_type: "application/pdf",
  uploaded_at: "2026-09-20T09:00:00Z",
  status: "active",
  retired_at: null,
  retired_by: null,
  retire_reason: null,
  replaced_by: null,
  replaced_by_name: null,
} as const;

describe("documents service", () => {
  it("listDocuments handles a paginated payload", async () => {
    fetchMock.mockResolvedValue(
      okResponse({ count: 1, next: null, previous: null, results: [DOC] })
    );

    const result = await listDocuments("abc");

    expect(result).toEqual([DOC]);
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/leave/leave-applications/abc/documents/"
    );
  });

  it("listDocuments handles a bare array", async () => {
    fetchMock.mockResolvedValue(okResponse([DOC]));

    expect(await listDocuments("abc")).toEqual([DOC]);
  });

  it("listDocuments surfaces rejected status via DocumentRequestError", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "gone" }), { status: 404 })
    );

    await expect(listDocuments("abc")).rejects.toMatchObject({
      status: 404,
      message: "gone",
    });
  });

  it("uploadDocument sends the file as multipart and returns the created doc", async () => {
    fetchMock.mockResolvedValue(okResponse(DOC));
    const file = new File(["x"], "cert.pdf", { type: "application/pdf" });

    const result = await uploadDocument("abc", file);

    expect(result).toEqual(DOC);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/leave/leave-applications/abc/documents/");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get("file")).toBe(file);
  });

  it("uploadDocument parses typed validation errors", async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          field: "file",
          code: "file_too_large",
          message: "Too big.",
        }),
        { status: 400 }
      )
    );

    const err = await uploadDocument("abc", new File([""], "x.png")).catch(
      (e: unknown) => e
    );

    expect(err).toBeInstanceOf(DocumentRequestError);
    expect(err).toMatchObject({
      status: 400,
      code: "file_too_large",
      field: "file",
      message: "Too big.",
    });
  });

  it("uploadDocument surfaces document_read_only as a 409", async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({ code: "document_read_only", detail: "Locked." }),
        { status: 409 }
      )
    );

    const err = await uploadDocument("abc", new File([""], "x.png")).catch(
      (e: unknown) => e
    );

    expect(err).toMatchObject({ status: 409, code: "document_read_only" });
  });

  it("removeDocument DELETEs the document endpoint", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    await removeDocument("abc", "doc-1");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/leave/leave-applications/abc/documents/doc-1/");
    expect(init.method).toBe("DELETE");
  });

  it("replaceDocument POSTs the file to the replace endpoint", async () => {
    fetchMock.mockResolvedValue(okResponse(DOC));
    const file = new File(["x"], "v2.pdf", { type: "application/pdf" });

    const result = await replaceDocument("abc", "doc-1", file);

    expect(result).toEqual(DOC);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/leave/leave-applications/abc/documents/doc-1/replace/");
    expect(init.method).toBe("POST");
    expect((init.body as FormData).get("file")).toBe(file);
  });

  it("getDocumentHistory GETs the history endpoint", async () => {
    fetchMock.mockResolvedValue(okResponse({ active: [], retired: [], events: [] }));

    const history = await getDocumentHistory("abc");

    expect(history).toEqual({ active: [], retired: [], events: [] });
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/leave/leave-applications/abc/documents/history/"
    );
  });

  it("documentContentUrl builds content and download URLs", () => {
    expect(documentContentUrl("abc", "doc-1")).toBe(
      "/api/leave/leave-applications/abc/documents/doc-1/content/"
    );
    expect(documentContentUrl("abc", "doc-1", true)).toBe(
      "/api/leave/leave-applications/abc/documents/doc-1/content/?download=1"
    );
  });
});

describe("document upload config endpoint", () => {
  it("returns the backend config when reachable", async () => {
    const config = {
      max_size_bytes: 5 * 1024 * 1024,
      allowed_content_types: ["application/pdf"],
    };
    fetchMock.mockResolvedValue(okResponse(config));

    await expect(getDocumentConfig()).resolves.toEqual(config);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/leave/leave-documents/config/");
  });

  it("falls back to defaults when the endpoint is unavailable", async () => {
    fetchMock.mockResolvedValue(new Response("boom", { status: 503 }));

    const config = await getDocumentConfig();

    expect(config.max_size_bytes).toBe(10 * 1024 * 1024);
    expect(config.allowed_content_types).toContain("application/pdf");
  });

  it("falls back to defaults on a non-JSON body", async () => {
    fetchMock.mockResolvedValue(new Response("not json", { status: 200 }));

    const config = await getDocumentConfig();

    expect(config.max_size_bytes).toBe(10 * 1024 * 1024);
  });
});

describe("formatFileSize", () => {
  it("formats bytes, KB and MB", () => {
    expect(formatFileSize(512)).toBe("512 B");
    expect(formatFileSize(2048)).toBe("2.0 KB");
    expect(formatFileSize(5 * 1024 * 1024)).toBe("5.0 MB");
  });
});