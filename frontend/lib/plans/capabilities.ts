import { cache } from "react";

import { apiClient } from "../api-client";
import type { PlanCapabilities } from "./types";

/**
 * What the signed-in caller may do with plans, as the backend sees it.
 *
 * Two independent answers live here: whether the plans approvals desk is open
 * to them (an active holder of an approver role, or HR), and how many blocks
 * of theirs are sitting in a confirmation window. Both are data questions
 * answered by team membership and persisted blocks, not by `User.role`, so the
 * server is the only place that can answer them. `null` means the read failed,
 * which callers treat as "not an approver" rather than guessing.
 *
 * Memoised per request because the layout, the sidebar badge and the plans
 * page itself all need it on one render.
 */
export const loadPlanCapabilities = cache(
  async (): Promise<PlanCapabilities | null> => {
    try {
      return await apiClient<PlanCapabilities>("/api/v1/plans/capabilities/");
    } catch {
      return null;
    }
  }
);
