import { apiErrorMessage } from "./utils";
import type { ApplyResult } from "./setup";

/**
 * Client-side calls for the setup hub's two write actions.
 *
 * Both are idempotent on the server, so the hub can offer them as plain buttons
 * without a "are you sure" on every use; the preview call is what stands in for
 * a confirmation, by showing exactly what an apply would create first.
 */
export async function previewDefaults(): Promise<ApplyResult> {
  return proxyPost<ApplyResult>("/api/hr/setup/apply-defaults", {
    dry_run: true,
  });
}

export async function applyDefaults(): Promise<ApplyResult> {
  return proxyPost<ApplyResult>("/api/hr/setup/apply-defaults", {});
}

export async function rolloverFinancialYear(): Promise<ApplyResult> {
  return proxyPost<ApplyResult>("/api/hr/setup/rollover", {});
}

async function proxyPost<T>(endpoint: string, body: unknown): Promise<T> {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(apiErrorMessage(data));
  }
  return response.json();
}
