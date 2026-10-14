import { apiClientUrl } from "./api-client";

/**
 * An HR account, as the superuser's user-management screen sees it.
 *
 * The shape is deliberately narrow: an account is a person, an email, a
 * password, and whether it is active. `role` and `is_superuser` are read-only
 * at this boundary — the endpoint exists to grant HR access and nothing more,
 * so the browser never needs to send a role back.
 */
export interface AdminUser {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: string;
  is_active: boolean;
  is_superuser: boolean;
}

export interface AdminUserInput {
  email: string;
  first_name?: string;
  last_name?: string;
  /** Required on create; blank on update keeps the current password. */
  password?: string;
  is_active?: boolean;
}

interface Paginated<T> {
  count: number;
  next: string | null;
  results: T[];
}

async function readAllPages<T>(endpoint: string): Promise<T[]> {
  const first = await apiClientUrl<Paginated<T>>(endpoint);
  const rows = [...first.results];
  let next = first.next;
  while (next) {
    const page = await apiClientUrl<Paginated<T>>(next);
    rows.push(...page.results);
    next = page.next;
  }
  return rows;
}

export async function listAdminUsers(): Promise<AdminUser[]> {
  return readAllPages<AdminUser>("/api/v1/admin-users/");
}

export async function getAdminUser(id: number | string): Promise<AdminUser> {
  return apiClientUrl<AdminUser>(`/api/v1/admin-users/${id}/`);
}
