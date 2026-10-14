import { apiClient } from "./api-client";
import type { SetupStatus, SetupTemplatesResponse } from "./setup";

/**
 * Server-side reads for the setup hub.
 *
 * Kept apart from :mod:`setup` because that module is imported by the client
 * component and must not pull `next/headers` into the browser bundle; these two
 * calls run in the server component that renders the hub.
 */
export async function getSetupStatus(): Promise<SetupStatus> {
  return apiClient<SetupStatus>("/api/v1/setup/status/");
}

export async function getSetupTemplates(): Promise<SetupTemplatesResponse> {
  return apiClient<SetupTemplatesResponse>("/api/v1/setup/templates/");
}
