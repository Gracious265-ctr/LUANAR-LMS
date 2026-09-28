import { cache } from "react";

import { apiClient } from "../api-client";
import type { ApprovalCapabilities } from "./types";

/**
 * Whether the signed-in caller may use the approver desk, as the backend sees
 * it: an active holder of at least one active approver role, or HR.
 *
 * This is a data question, not a role-string question — the answer lives in a
 * team membership or an institution-wide holding — so the server is the only
 * place that can answer it. `null` means the read failed, which callers treat
 * as "not an approver" rather than guessing.
 *
 * Memoised per request for the same reason as `getCurrentUser`: the layout, the
 * sidebar, and the page itself all need this on one render, and the sidebar
 * used to ask the browser for it again after every navigation.
 */
export const loadApprovalCapabilities = cache(
  async (): Promise<ApprovalCapabilities | null> => {
    try {
      return await apiClient<ApprovalCapabilities>(
        "/api/v1/approvals/capabilities/"
      );
    } catch {
      return null;
    }
  }
);
