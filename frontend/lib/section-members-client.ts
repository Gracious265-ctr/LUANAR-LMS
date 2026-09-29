import type { SectionMember } from "./workflows";
import { apiErrorMessage } from "./utils";

/**
 * Client-side writes for who can act for a section.
 *
 * Kept out of `teams.ts` deliberately: `teams.ts` imports the server-only
 * `api-client` (for `next/headers`), so it cannot be bundled into a client
 * component. Membership is edited interactively on the teams list, which is
 * the only place these are used.
 */
export async function listSectionMembers(section: number): Promise<SectionMember[]> {
  return readAllPages<SectionMember>(`/api/hr/section-members/?section=${section}`);
}

export async function addSectionMember(section: number, user: number): Promise<void> {
  await proxyWrite("/api/hr/section-members", "POST", { section, user });
}

export async function removeSectionMember(id: number): Promise<void> {
  await proxyWrite(`/api/hr/section-members/${id}`, "DELETE");
}

interface Page<T> {
  count: number;
  next: string | null;
  results: T[];
}

/** Whole list, not page one: a roster is short-lived and should never truncate. */
async function readAllPages<T>(endpoint: string): Promise<T[]> {
  const first = await proxyRead<Page<T>>(endpoint);
  const rows = [...first.results];
  let next = first.next;
  while (next) {
    const page = await proxyRead<Page<T>>(next);
    rows.push(...page.results);
    next = page.next;
  }
  return rows;
}

async function proxyRead<T>(endpoint: string): Promise<T> {
  const response = await fetch(endpoint);
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(apiErrorMessage(data));
  }
  return response.json();
}

async function proxyWrite(
  endpoint: string,
  method: "POST" | "DELETE",
  body?: unknown
): Promise<void> {
  const response = await fetch(endpoint, {
    method,
    headers: { "Content-Type": "application/json" },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(apiErrorMessage(data));
  }
}