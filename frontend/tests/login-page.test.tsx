import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "@/app/(auth)/login/page";

const push = vi.fn();
const refresh = vi.fn();
let query = "";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
  useSearchParams: () => new URLSearchParams(query),
}));

beforeEach(() => {
  vi.clearAllMocks();
  query = "";
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

async function signIn() {
  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: "someone@luanar.ac.mw" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "correct horse battery staple" },
  });
  fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
}

describe("login page", () => {
  it("lands on the app launcher when no redirect is requested", async () => {
    render(<LoginPage />);

    await signIn();

    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
  });

  it("honours an explicit redirect target", async () => {
    query = "redirect=/leave/drafts";
    render(<LoginPage />);

    await signIn();

    await waitFor(() => expect(push).toHaveBeenCalledWith("/leave/drafts"));
  });
});
