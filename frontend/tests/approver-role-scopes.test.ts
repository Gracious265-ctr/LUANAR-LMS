import { describe, expect, it } from "vitest";

import {
  HISTORY_SCOPE_LABELS,
  HISTORY_SCOPES,
  historyScopeLabel,
} from "@/lib/approver-role-scopes";
import { HISTORY_SCOPES as SERVER_SCOPES } from "@/lib/approver-roles";
import {
  HISTORY_SCOPES as CLIENT_SCOPES,
  historyScopeLabel as clientHistoryScopeLabel,
} from "@/lib/approver-roles-client";

describe("history scopes", () => {
  it("labels every scope the picker offers", () => {
    for (const scope of HISTORY_SCOPES) {
      expect(historyScopeLabel(scope)).not.toBe(scope);
      expect(HISTORY_SCOPE_LABELS[scope]).toBeTruthy();
    }
  });

  it("falls back to a scope this build does not know", () => {
    // A scope added to the backend after this build must render as itself
    // rather than as `undefined` or by crashing.
    expect(historyScopeLabel("same_campus")).toBe("same_campus");
  });

  it("rejects a scope the picker must not offer", () => {
    expect(HISTORY_SCOPES).not.toContain("same_team");
  });

  it("is one list, shared by the client picker and the server reader", () => {
    // The constants live in an import-free module precisely so a client
    // component can read them without dragging the server-only API client in.
    expect(CLIENT_SCOPES).toBe(HISTORY_SCOPES);
    expect(SERVER_SCOPES).toBe(HISTORY_SCOPES);
    expect(clientHistoryScopeLabel).toBe(historyScopeLabel);
  });
});
