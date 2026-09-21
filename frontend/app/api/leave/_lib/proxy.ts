import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function proxyRequest(
  method: string,
  path: string,
  body?: unknown,
  isFormData = false
) {
  return apiFetch(method, path, { body, isFormData });
}