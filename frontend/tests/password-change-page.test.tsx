/**
 * The account page's password form, and the client helper behind it.
 *
 * The interesting cases are the ones the user has to be told about: the current
 * password is wrong, the new one fails a validator, the two do not match, and
 * the success case that has to end in signing out. The last one is why the
 * helper clears the cookies itself — the server has already revoked the tokens
 * by the time the 200 arrives, so a page that merely navigates would leave a
 * dead cookie behind and show an unexplained login screen.
 */

import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PasswordChangeForm } from "@/components/account/password-change-form";
import { changePassword } from "@/lib/password-change";

vi.mock("@/lib/password-change", () => ({
  changePassword: vi.fn(),
}));

const mockedChange = vi.mocked(changePassword);

// The form navigates on success, so the router needs to be observable. The
// global setup mock creates its vi.fn()s inside the factory, which means they
// are not reachable from a test, hence re-mocking it here.
const { mockPush, mockRefresh } = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockRefresh: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard/account",
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    refresh: mockRefresh,
    back: vi.fn(),
    forward: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

function renderForm() {
  return render(<PasswordChangeForm />);
}

function fillForm(
  current = "current pass phrase 7",
  next = "a whole new pass phrase 9",
  confirm = "a whole new pass phrase 9",
) {
  fireEvent.change(screen.getByLabelText("Current password"), {
    target: { value: current },
  });
  fireEvent.change(screen.getByLabelText("New password"), {
    target: { value: next },
  });
  fireEvent.change(screen.getByLabelText("Confirm new password"), {
    target: { value: confirm },
  });
}

function submit() {
  fireEvent.click(screen.getByRole("button", { name: /change password/i }));
}

describe("PasswordChangeForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedChange.mockResolvedValue({ ok: true, detail: "Password changed." });
  });

  it("asks for the current password as well as the new one", () => {
    renderForm();

    expect(screen.getByLabelText("Current password")).toBeInTheDocument();
    expect(screen.getByLabelText("New password")).toBeInTheDocument();
    expect(screen.getByLabelText("Confirm new password")).toBeInTheDocument();
  });

  it("sends all three values", async () => {
    renderForm();
    fillForm();

    submit();

    await waitFor(() =>
      expect(mockedChange).toHaveBeenCalledWith(
        "current pass phrase 7",
        "a whole new pass phrase 9",
        "a whole new pass phrase 9",
      ),
    );
  });

  it("catches a mismatch before the request is made", async () => {
    // Retyping a field you cannot see is the common mistake, and a round trip
    // teaches the user nothing about it.
    renderForm();
    fillForm("current pass phrase 7", "one pass phrase", "another pass phrase");

    submit();

    expect(
      await screen.findByText("The two passwords do not match."),
    ).toBeInTheDocument();
    expect(mockedChange).not.toHaveBeenCalled();
  });

  it("puts a mismatch message on the confirmation field, not the form", async () => {
    renderForm();
    fillForm("current pass phrase 7", "one pass phrase", "another pass phrase");

    submit();
    await screen.findByText("The two passwords do not match.");

    // The complaint is about the confirmation, so it belongs beside it.
    const label = screen.getByText("Confirm new password").closest("div");
    expect(label?.textContent).toContain("The two passwords do not match.");
  });

  it("shows a wrong current password against the current field", async () => {
    mockedChange.mockResolvedValue({
      ok: false,
      error: "Your current password is not correct.",
      field: "current_password",
    });
    renderForm();
    fillForm();

    submit();

    expect(
      await screen.findByText("Your current password is not correct."),
    ).toBeInTheDocument();
  });

  it("shows a rejected new password against the new field", async () => {
    mockedChange.mockResolvedValue({
      ok: false,
      error: "This password is too short.",
      field: "new_password",
    });
    renderForm();
    fillForm();

    submit();

    expect(await screen.findByText("This password is too short.")).toBeInTheDocument();
  });

  it("falls back to a form-level message when the field is unknown", async () => {
    mockedChange.mockResolvedValue({ ok: false, error: "Something went wrong." });
    renderForm();
    fillForm();

    submit();

    expect(await screen.findByText("Something went wrong.")).toBeInTheDocument();
  });

  it("returns to the sign-in page explaining the sign-out", async () => {
    renderForm();
    fillForm();

    submit();

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/login?changed=1"));
    // refresh() as well: the dashboard layout is a server component holding the
    // session that just ended.
    expect(mockRefresh).toHaveBeenCalled();
  });

  it("warns that the change signs every session out, before it happens", () => {
    renderForm();

    // Saying it only afterwards is a notice, not a warning.
    expect(screen.getByText(/signs you out everywhere/i)).toBeInTheDocument();
  });

  it("clears the error when the person starts editing again", async () => {
    mockedChange.mockResolvedValue({
      ok: false,
      error: "Your current password is not correct.",
      field: "current_password",
    });
    renderForm();
    fillForm();
    submit();
    await screen.findByText("Your current password is not correct.");

    fireEvent.change(screen.getByLabelText("Current password"), {
      target: { value: "typo fixed" },
    });

    expect(
      screen.queryByText("Your current password is not correct."),
    ).not.toBeInTheDocument();
  });
});
