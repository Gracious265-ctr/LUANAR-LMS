import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  confirmPasswordSet,
  requestPasswordSetLink,
  validatePasswordSetToken,
} from "@/lib/password-set";
import SetPasswordPage from "@/app/(auth)/set-password/page";
import ForgotPasswordPage from "@/app/(auth)/forgot-password/page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(currentTokenQuery),
}));

vi.mock("@/lib/password-set", () => ({
  confirmPasswordSet: vi.fn(),
  validatePasswordSetToken: vi.fn(),
  requestPasswordSetLink: vi.fn(),
}));

const mockedConfirm = vi.mocked(confirmPasswordSet);
const mockedValidate = vi.mocked(validatePasswordSetToken);
const mockedRequest = vi.mocked(requestPasswordSetLink);

let currentTokenQuery = "";

describe("set-password page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    currentTokenQuery = "token=abc123";
    mockedValidate.mockResolvedValue({ valid: true });
    mockedConfirm.mockResolvedValue({ ok: true, detail: "Password set. You can sign in now." });
  });

  async function renderWithToken(query: string) {
    currentTokenQuery = query;
    render(<SetPasswordPage />);
    // The pre-flight resolves before the form appears; waiting for it is what
    // makes the "dead link" assertions meaningful rather than racing.
    await waitFor(() => expect(mockedValidate).toHaveBeenCalled());
  }

  it("asks whether the link is live before showing a form", async () => {
    render(<SetPasswordPage />);

    expect(await screen.findByLabelText("Password")).toBeInTheDocument();
    expect(mockedValidate).toHaveBeenCalledWith("abc123");
  });

  it("sets the password and says so", async () => {
    await renderWithToken("token=abc123");
    await screen.findByLabelText("Password");

    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "correct horse battery staple" },
    });
    fireEvent.change(screen.getByLabelText("Confirm password"), {
      target: { value: "correct horse battery staple" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Set password" }));

    await waitFor(() =>
      expect(mockedConfirm).toHaveBeenCalledWith(
        "abc123",
        "correct horse battery staple"
      )
    );
    expect(await screen.findByText(/password set/i)).toBeInTheDocument();
  });

  it("refuses a mismatched confirmation without calling the backend", async () => {
    await renderWithToken("token=abc123");
    await screen.findByLabelText("Password");

    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "one thing" } });
    fireEvent.change(screen.getByLabelText("Confirm password"), {
      target: { value: "another thing" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Set password" }));

    expect(await screen.findByText(/do not match/i)).toBeInTheDocument();
    expect(mockedConfirm).not.toHaveBeenCalled();
  });

  it("offers a new link instead of a form when the link is dead", async () => {
    mockedValidate.mockResolvedValue({ valid: false });

    render(<SetPasswordPage />);

    expect(await screen.findByText(/no longer valid/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /request a new link/i })).toHaveAttribute(
      "href",
      "/forgot-password"
    );
    expect(screen.queryByLabelText("Password")).not.toBeInTheDocument();
  });

  it("treats a missing token as a dead link rather than asking for a password", async () => {
    currentTokenQuery = "";
    render(<SetPasswordPage />);

    expect(await screen.findByText(/no longer valid/i)).toBeInTheDocument();
    expect(mockedValidate).not.toHaveBeenCalled();
    expect(mockedConfirm).not.toHaveBeenCalled();
  });

  it("scrubs the token out of the address bar", async () => {
    const replaceState = vi.spyOn(window.history, "replaceState");

    await renderWithToken("token=abc123");
    await screen.findByLabelText("Password");

    expect(replaceState).toHaveBeenCalled();
    const [, , url] = replaceState.mock.calls[0];
    expect(String(url)).not.toContain("abc123");
  });

  it("stays usable when the router drops the token after the scrub", async () => {
    // The regression that let a live link read as "no longer valid". The page
    // scrubs ?token= from the address bar, and in a real browser the router
    // then reports no token on the next read. Re-deriving the token from
    // searchParams on every effect run meant the second read was empty, so a
    // perfectly good link was declared dead. A constant mock could never catch
    // it, because it never dropped the token.
    currentTokenQuery = "token=abc123";
    const { rerender } = render(<SetPasswordPage />);
    await waitFor(() => expect(mockedValidate).toHaveBeenCalledWith("abc123"));

    // What the scrub does to the router's view of the URL: no token, now.
    currentTokenQuery = "";
    rerender(<SetPasswordPage />);

    expect(await screen.findByLabelText("Password")).toBeInTheDocument();
    expect(
      screen.queryByText(/no longer valid/i),
    ).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "a long enough passphrase 1" },
    });
    fireEvent.change(screen.getByLabelText("Confirm password"), {
      target: { value: "a long enough passphrase 1" },
    });
    fireEvent.click(screen.getByRole("button", { name: /set password/i }));

    // The ref, not the URL, is what confirm must send — otherwise the password
    // is submitted against an empty token and the backend refuses it.
    await waitFor(() =>
      expect(mockedConfirm).toHaveBeenCalledWith("abc123", "a long enough passphrase 1"),
    );
  });

  it("keeps working after the token is out of the URL", async () => {
    const replaceState = vi
      .spyOn(window.history, "replaceState")
      .mockImplementation(() => {});
    await renderWithToken("token=abc123");
    await screen.findByLabelText("Password");

    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "a good long one" } });
    fireEvent.change(screen.getByLabelText("Confirm password"), {
      target: { value: "a good long one" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Set password" }));

    // The ref holds the token, not the scrubbed URL — a real scrub must not cost
    // the person the ability to finish.
    await waitFor(() => expect(mockedConfirm).toHaveBeenCalledWith("abc123", "a good long one"));
    replaceState.mockRestore();
  });
});

describe("forgot-password page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedRequest.mockResolvedValue({ ok: true });
  });

  it("asks for a link and shows the same message whatever the answer", async () => {
    render(<ForgotPasswordPage />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "someone@luanar.ac.mw" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send link/i }));

    await waitFor(() =>
      expect(mockedRequest).toHaveBeenCalledWith("someone@luanar.ac.mw")
    );
    // The wording must not promise delivery: the backend cannot tell this page
    // whether the address has an account, and that is the point.
    expect(await screen.findByText(/if that address has an account/i)).toBeInTheDocument();
  });

  it("surfaces a failure without claiming anything was sent", async () => {
    mockedRequest.mockResolvedValue({ ok: false, error: "Could not send the link." });

    render(<ForgotPasswordPage />);
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "someone@luanar.ac.mw" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send link/i }));

    expect(await screen.findByText(/could not send the link/i)).toBeInTheDocument();
    expect(screen.queryByText(/if that address has an account/i)).not.toBeInTheDocument();
  });
});
