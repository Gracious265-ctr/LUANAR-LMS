import type { Reassignment, ReassignmentInput } from "./reassignments";
import { apiErrorMessage } from "./utils";

export async function reassignApplication(
  input: ReassignmentInput
): Promise<Reassignment> {
  return proxyPost<Reassignment>("/api/hr/reassignments", input);
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