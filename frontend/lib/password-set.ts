/**
 * The first password, and the forgotten one.
 *
 * HR creates accounts, and HR cannot know a password, so a new employee arrives
 * here with no way in until they follow the link in their welcome mail. These
 * helpers go through the same-origin proxy routes rather than Django directly:
 * the browser must never learn the Django URL, and the token travels once, in a
 * POST body or a query string this module is the only place that assembles.
 *
 * Every function returns a discriminated result instead of throwing. The two
 * failure modes here look identical from the outside on purpose — a dead link and
 * a wrong guess must not be tellable apart by an attacker — and the pages need to
 * branch on the outcome anyway.
 */

export type PasswordSetOutcome =
  | { ok: true; detail?: string }
  | { ok: false; error: string; expired?: boolean };

export type PasswordSetValidity = { valid: boolean };

async function readMessage(response: Response, fallback: string): Promise<string> {
  const data = await response.json().catch(() => null);
  if (typeof data?.detail === "string") return data.detail;
  if (Array.isArray(data?.detail) && typeof data.detail[0] === "string") {
    return data.detail[0];
  }
  return fallback;
}

/**
 * Ask for a link. The answer is the same whether or not the address has an
 * account, so there is nothing to branch on — which is the point: the page
 * cannot be used to find out who works here.
 */
export async function requestPasswordSetLink(email: string): Promise<PasswordSetOutcome> {
  try {
    const response = await fetch("/api/auth/password-set/request", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });

    if (!response.ok) {
      return { ok: false, error: await readMessage(response, "Could not send the link.") };
    }
    const data = await response.json().catch(() => null);
    return { ok: true, detail: data?.detail };
  } catch {
    return { ok: false, error: "An error occurred. Please try again." };
  }
}

/** Whether a link is still live, asked before anyone is invited to type a password. */
export async function validatePasswordSetToken(
  token: string
): Promise<PasswordSetValidity | null> {
  try {
    const response = await fetch(
      `/api/auth/password-set/validate?token=${encodeURIComponent(token)}`,
      { cache: "no-store" }
    );
    if (!response.ok) return null;
    const data = await response.json().catch(() => null);
    return { valid: Boolean(data?.valid) };
  } catch {
    return null;
  }
}

export async function confirmPasswordSet(
  token: string,
  password: string
): Promise<PasswordSetOutcome> {
  try {
    const response = await fetch("/api/auth/password-set/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, password }),
    });

    if (response.ok) {
      const data = await response.json().catch(() => null);
      return { ok: true, detail: data?.detail };
    }
    // Django distinguishes "this link is dead" from "that password is not
    // acceptable", and the page can too — but only because both come back as a
    // message to show, never as a hint about the token.
    const error = await readMessage(response, "Could not set the password.");
    return { ok: false, error, expired: /no longer valid/i.test(error) };
  } catch {
    return { ok: false, error: "An error occurred. Please try again." };
  }
}
