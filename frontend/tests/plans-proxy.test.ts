import { NextResponse } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/app/api/_lib/api-fetch", () => ({
  // Forwarded as a tuple so a handler that passes no options stays a two-argument
  // call: the assertions below care that the proxy forwards exactly what it read.
  apiFetch: (...args: [string, string, unknown?]) => mockedApiFetch(...args),
}));

import { GET as adminList } from "@/app/api/plans/admin/route";
import { POST as approvalDecision } from "@/app/api/plans/approvals/[id]/decision/route";
import { GET as approvalQueue } from "@/app/api/plans/approvals/route";
import { GET as approvalDetailRoute } from "@/app/api/plans/approvals/[id]/route";
import { POST as blockConfirm } from "@/app/api/plans/[id]/blocks/[blockId]/confirm/route";
import { POST as blockRelease } from "@/app/api/plans/[id]/blocks/[blockId]/release/route";
import { GET as planDetail } from "@/app/api/plans/[id]/route";
import { POST as planSubmit } from "@/app/api/plans/[id]/submit/route";
import { GET as capabilities } from "@/app/api/plans/capabilities/route";
import { GET as pendingConfirmations } from "@/app/api/plans/pending-confirmations/route";
import { GET as planList, POST as planCreate } from "@/app/api/plans/route";
import { GET as readSettings, PATCH as writeSettings } from "@/app/api/plans/settings/route";

const mockedApiFetch = vi.fn<(...args: unknown[]) => Promise<NextResponse>>(
  async () => NextResponse.json({ ok: true })
);

function getRequest(query = "") {
  return new Request(`http://localhost:3000/api/plans${query}`);
}

function jsonRequest(query: string, body: unknown) {
  return new Request(`http://localhost:3000/api/plans${query}`, {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

const blockParams = Promise.resolve({ id: "7", blockId: "11" });
const planParams = Promise.resolve({ id: "7" });

describe("plans proxy routes", () => {
  beforeEach(() => {
    mockedApiFetch.mockClear();
  });

  it("reads the caller's own plans when no scope is asked for", async () => {
    await planList(getRequest());

    expect(mockedApiFetch).toHaveBeenCalledWith("GET", "plans/?scope=mine");
  });

  it("keeps a known scope and narrows an unknown one to mine", async () => {
    await planList(getRequest("?scope=department"));
    await planList(getRequest("?scope=everyone"));
    await planList(getRequest("?scope=mine&page=2"));

    expect(mockedApiFetch).toHaveBeenNthCalledWith(1, "GET", "plans/?scope=department");
    // A hand-edited scope cannot quietly relabel the caller's own plans as a
    // team's, and the route forwards one parameter at a time.
    expect(mockedApiFetch).toHaveBeenNthCalledWith(2, "GET", "plans/?scope=mine");
    expect(mockedApiFetch).toHaveBeenNthCalledWith(3, "GET", "plans/?scope=mine");
  });

  it("creates a plan with the body it was given", async () => {
    const body = { reason: "Fieldwork", blocks: [] };

    await planCreate(jsonRequest("", body));

    expect(mockedApiFetch).toHaveBeenCalledWith("POST", "plans/", { body });
  });

  it("waits for the plan id before reading or acting on a plan", async () => {
    await planDetail(getRequest("/7"), { params: planParams });
    await planSubmit(getRequest("/7/submit"), { params: planParams });
    await blockConfirm(getRequest("/7/blocks/11/confirm"), { params: blockParams });
    await blockRelease(getRequest("/7/blocks/11/release"), { params: blockParams });

    expect(mockedApiFetch).toHaveBeenNthCalledWith(1, "GET", "plans/7/");
    expect(mockedApiFetch).toHaveBeenNthCalledWith(2, "POST", "plans/7/submit/");
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      3,
      "POST",
      "plans/7/blocks/11/confirm/"
    );
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      4,
      "POST",
      "plans/7/blocks/11/release/"
    );
  });

  it("defaults the approval queue to the first pending page", async () => {
    await approvalQueue(getRequest("/approvals"));

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "GET",
      "plans/approvals/?tab=pending&page=1"
    );
  });

  it("passes the queue tab and page the caller asked for", async () => {
    await approvalQueue(getRequest("/approvals?tab=decided&page=3"));

    expect(mockedApiFetch).toHaveBeenCalledWith(
      "GET",
      "plans/approvals/?tab=decided&page=3"
    );
  });

  it("reads one plan from the approver's own view", async () => {
    await approvalDetailRoute(getRequest("/approvals/7"), { params: planParams });

    expect(mockedApiFetch).toHaveBeenCalledWith("GET", "plans/approvals/7/");
  });

  it("forwards a decision verbatim, stage version included", async () => {
    const body = { action: "reject", comment: "Not this term", stage_version: 4 };

    await approvalDecision(jsonRequest("/approvals/7/decision", body), {
      params: planParams,
    });

    expect(mockedApiFetch).toHaveBeenCalledWith("POST", "plans/approvals/7/decision/", {
      body,
    });
  });

  it("reads pending confirmations and capabilities without a query", async () => {
    await pendingConfirmations();
    await capabilities();

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      "GET",
      "plans/pending-confirmations/"
    );
    expect(mockedApiFetch).toHaveBeenNthCalledWith(2, "GET", "plans/capabilities/");
  });

  it("reads and writes the deadline settings", async () => {
    const body = { minimum_notice_days: 7 };

    await readSettings();
    await writeSettings(
      new Request("http://localhost:3000/api/plans/settings", {
        method: "PATCH",
        body: JSON.stringify(body),
      })
    );

    expect(mockedApiFetch).toHaveBeenNthCalledWith(1, "GET", "plans/settings/");
    expect(mockedApiFetch).toHaveBeenNthCalledWith(2, "PATCH", "plans/settings/", {
      body,
    });
  });

  it("always pages the admin table and adds only the filters given", async () => {
    await adminList(getRequest("/admin"));
    await adminList(getRequest("/admin?status=pending&block_status=awaiting&page=2"));
    await adminList(getRequest("/admin?status=approved"));

    expect(mockedApiFetch).toHaveBeenNthCalledWith(1, "GET", "plans/admin/?page=1");
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      "GET",
      "plans/admin/?page=2&status=pending&block_status=awaiting"
    );
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      3,
      "GET",
      "plans/admin/?page=1&status=approved"
    );
  });
});
