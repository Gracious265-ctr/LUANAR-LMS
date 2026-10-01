/**
 * Changing a password from a live session.
 *
 * Distinct from lib/password-set, which is about a *token* emailed to someone
 * who cannot sign in. This is the one case where the caller already has a
 * session, which changes two things:
 *
 * - the request goes through the same-origin proxy that carries the access
 *   cookie, like every other authenticated write (see app/api/hr/employees);
 * - the caller's own token stops working the moment it succeeds, so this module
 *   also clears the cookies. Leaving a dead access cookie behind would send the
 *   next request through a refresh that is equally dead, and the user would see
 *   a bare login page instead of being told what happened.
 *
 * Returns a discriminated result rather than throwing, matching password-set,
 * and for the same reason: the page branches on the outcome, and a validator
 * message about the new password is a different thing to show than a refusal of
 * the current one.
 */

export type PasswordChangeOutcome =
  | { ok: true; detail?: string }
  | { ok: false; error: string; field?: "current_password" | "new_password" };

type DjangoErrorBody = {
  detail?: string | string[];
  confirm_password?: string[];
  current_password?: string[];
  new_password?: string[];
};

/**
 * Which field the message is about, when the backend says.
 *
 * Worth separating from the message: "Your current password is not correct" and
 * a validator's "This password is too short" both arrive as `detail`, but only
 * one of them is answered by retyping the field the person was not looking at.
 */
/**
 * The key the backend blamed, and the message it gave, together.
 *
 * They are read as a pair because they do not always share a key: a mismatch
 * arrives under `confirm_password` but belongs beside the *new* password, so
 * looking the message up by the returned field would find nothing. Two lookups
 * that must agree is one bug away from a blank error box.
 */
function readBlame(data: DjangoErrorBody | null) {
  if (!data) return {};

  if (Array.isArray(data.current_password)) {
    return {
      field: "current_password" as const,
      message: data.current_password[0],
    };
  }
  // Checked before new_password for the same reason it is mapped after: the
  // confirm field's messages are about the new password.
  if (Array.isArray(data.confirm_password)) {
    return {
      field: "new_password" as const,
      message: data.confirm_password[0],
    };
  }
  if (Array.isArray(data.new_password)) {
    return {
      field: "new_password" as const,
      message: data.new_password[0],
    };
  }
  return {};
}

function readMessage(data: DjangoErrorBody | null, fallback: string): string {
  if (typeof data?.detail === "string") return data.detail;
  if (Array.isArray(data?.detail) && typeof data.detail[0] === "string") {
    return data.detail[0];
  }
  const blamed = readBlame(data);
  return typeof blamed.message === "string" ? blamed.message : fallback;
}

export async function changePassword(
  currentPassword: string,
  newPassword: string,
  confirmPassword: string,
): Promise<PasswordChangeOutcome> {
  try {
    const response = await fetch("/api/auth/password-change", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      }),
    });

    if (!response.ok) {
      const data = await response.json().catch(() => null);
      const blamed = readBlame(data);
      return {
        ok: false,
        error: readMessage(data, "Could not change your password."),
        field: blamed.field,
      };
    }

    const data = await response.json().catch(() => null);
    const detail = typeof data?.detail === "string" ? data.detail : undefined;

    // The session is already invalid server-side. Clearing the cookies here is
    // what turns "your other sessions are signed out" into "this one is too",
    // instead of leaving the browser to discover it on the next click.
    await clearAuthCookies();

    return { ok: true, detail };
  } catch {
    return { ok: false, error: "An error occurred. Please try again." };
  }
}

/**
 * Drop the access and refresh cookies.
 *
 * Best-effort by design: if this call fails, the server has *still* revoked the
 * tokens, so the outcome the user cares about holds either way. A failure here
 * must not turn a successful password change into a reported error.
 */
async function clearAuthCookies(): Promise<void> {
  try {
    await fetch("/api/auth/logout", { method: "POST" });
  } catch {
    // Deliberately swallowed — see above.
  }
}
