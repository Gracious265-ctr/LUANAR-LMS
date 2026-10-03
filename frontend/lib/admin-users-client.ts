import type { AdminUser, AdminUserInput } from "./admin-users";
import { apiErrorMessage } from "./utils";

export async function createAdminUser(
  input: AdminUserInput
): Promise<AdminUser> {
  return send<AdminUser>("/api/admin/users", "POST", input);
}

export async function updateAdminUser(
  id: number | string,
  input: Partial<AdminUserInput>
): Promise<AdminUser> {
  return send<AdminUser>(`/api/admin/users/${id}`, "PATCH", input);
}

async function send<T>(
  endpoint: string,
  method: "POST" | "PATCH",
  body: unknown
): Promise<T> {
  const response = await fetch(endpoint, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(apiErrorMessage(data));
  }
  return response.json();
}
