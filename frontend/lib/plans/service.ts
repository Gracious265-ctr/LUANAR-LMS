import { apiErrorMessage } from "@/lib/utils";

import type {
  CreatePlanInput,
  LeavePlan,
  PlanApplicationResult,
  PlanListResponse,
  PlanScope,
  TeamPlansResponse,
} from "./types";

/**
 * Browser-side access to the Leave Plans API.
 *
 * Every call goes through the app's own `/api/plans/*` proxies, which forward to
 * Django with the session cookie — the same shape the Leave module uses — so no
 * bearer token is handled in the browser.
 */

async function parse<T>(res: Response, fallback: string): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(apiErrorMessage(body) || fallback);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function listPlans(): Promise<LeavePlan[]> {
  const res = await fetch("/api/plans/", { credentials: "include" });
  const data = await parse<PlanListResponse | LeavePlan[]>(
    res,
    "Failed to load your plans"
  );
  return Array.isArray(data) ? data : (data.results ?? []);
}

export async function createPlan(
  input: CreatePlanInput
): Promise<LeavePlan> {
  const res = await fetch("/api/plans/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(input),
  });
  return parse<LeavePlan>(res, "Failed to create the plan");
}

export async function getPlan(id: string): Promise<LeavePlan> {
  const res = await fetch(`/api/plans/${id}/`, { credentials: "include" });
  return parse<LeavePlan>(res, "Failed to load the plan");
}

/** Cancelling is a delete on the owner's own plan (spec 3.2). */
export async function cancelPlan(id: string): Promise<void> {
  const res = await fetch(`/api/plans/${id}/`, {
    method: "DELETE",
    credentials: "include",
  });
  await parse<void>(res, "Failed to cancel the plan");
}

/** Turns a plan into a draft application and returns its id. */
export async function applyPlan(
  id: string
): Promise<PlanApplicationResult> {
  const res = await fetch(`/api/plans/${id}/apply/`, {
    method: "POST",
    credentials: "include",
  });
  return parse<PlanApplicationResult>(res, "Failed to start the application");
}

export async function getScopeOptions(): Promise<PlanScope[]> {
  const res = await fetch("/api/plans/scope-options/", { credentials: "include" });
  const data = await parse<PlanScope[]>(res, "Failed to load calendar scopes");
  return Array.isArray(data) ? data : [];
}

export async function getTeamPlans(
  options: { scope?: string; month?: string } = {}
): Promise<TeamPlansResponse> {
  const url = new URL("/api/plans/team/", window.location.origin);
  if (options.scope) url.searchParams.set("scope", options.scope);
  if (options.month) url.searchParams.set("month", options.month);
  const res = await fetch(url.toString(), { credentials: "include" });
  return parse<TeamPlansResponse>(res, "Failed to load the team calendar");
}
