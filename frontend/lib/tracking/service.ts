import type { TrackingResponse, TrackingResult } from "./types";

/**
 * Fetch the tracking payload for the current user's submitted application via
 * the Next.js proxy. Surfaces a typed result so the UI can distinguish a
 * missing application (404), an unsubmitted draft (409 ``application_not_submitted``)
 * from network/other failures — the three cases render differently.
 */
export async function fetchTracking(applicationId: string): Promise<TrackingResult> {
  try {
    const res = await fetch(
      `/api/leave/leave-applications/${encodeURIComponent(applicationId)}/tracking/`,
      { credentials: "include" }
    );

    if (res.status === 404) {
      return { ok: false, kind: "not_found" };
    }

    const data = await res.json().catch(() => ({}));

    if (res.status === 409) {
      const code = (data as { code?: string }).code;
      if (code === "application_not_submitted") {
        return { ok: false, kind: "not_submitted" };
      }
      return { ok: false, kind: "error", message: "The application cannot be tracked right now." };
    }

    if (!res.ok) {
      const message =
        (data as { detail?: string }).detail ||
        "Failed to load tracking information.";
      return { ok: false, kind: "error", message };
    }

    return { ok: true, data: data as TrackingResponse };
  } catch {
    return {
      ok: false,
      kind: "error",
      message: "Could not reach the server. Check your connection and try again.",
    };
  }
}

/**
 * Accept the rejection on an application, closing it without resubmitting.
 *
 * The backend keeps the status (`rejected`) and records the acceptance on the
 * row, so the caller re-reads the tracking payload afterwards rather than
 * guessing the new state from this response.
 */
export async function acceptRejection(
  applicationId: string
): Promise<{ ok: true } | { ok: false; message: string }> {
  try {
    const res = await fetch(
      `/api/leave/leave-applications/${encodeURIComponent(applicationId)}/accept-rejection/`,
      { method: "POST", credentials: "include" }
    );

    if (res.ok) return { ok: true };

    const data = await res.json().catch(() => ({}));
    if (res.status === 409) {
      return {
        ok: false,
        message: "This application is not rejected.",
      };
    }
    return {
      ok: false,
      message:
        (data as { detail?: string }).detail ||
        "The rejection could not be accepted. Try again.",
    };
  } catch {
    return {
      ok: false,
      message: "Could not reach the server. Check your connection and try again.",
    };
  }
}