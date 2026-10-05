import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EntitlementForm } from "@/components/hr/entitlement-form";
import type { Entitlement } from "@/lib/entitlements";

const band: Entitlement = {
  id: 3,
  grade_start: "A",
  grade_end: "C",
  days: 21,
  effective_from: "2026-01-01",
  leave_type: 1,
  leave_type_name: "Annual Leave",
};

function fillForm() {
  fireEvent.change(screen.getByLabelText("Grade start"), {
    target: { value: "V" },
  });
  fireEvent.change(screen.getByLabelText("Grade end"), {
    target: { value: "Z" },
  });
  fireEvent.change(screen.getByLabelText("Annual days"), {
    target: { value: "30" },
  });
  fireEvent.change(screen.getByLabelText("Effective from"), {
    target: { value: "2026-01-01" },
  });
}

function submitForm() {
  // The form marks every field required, so jsdom blocks submission until they
  // are filled in.
  fillForm();
  fireEvent.click(screen.getByRole("button", { name: /entitlement/i }));
}

describe("EntitlementForm", () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => band,
    }) as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("has no leave-type picker, because every entitlement grants annual leave", () => {
    render(
      <EntitlementForm endpoint="/api/v1/entitlements/" method="POST" />
    );

    expect(screen.getByLabelText("Grade start")).toBeInTheDocument();
    expect(screen.getByLabelText("Grade end")).toBeInTheDocument();
    expect(screen.getByLabelText("Annual days")).toBeInTheDocument();
    expect(screen.getByLabelText("Effective from")).toBeInTheDocument();
    expect(screen.queryByLabelText("Leave type")).not.toBeInTheDocument();
  });

  it("says the band grants annual leave and points at Leave Rules", () => {
    render(
      <EntitlementForm endpoint="/api/v1/entitlements/" method="POST" />
    );

    expect(screen.getByText(/Annual Leave/)).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "Leave Rules" });
    expect(link.getAttribute("href")).toBe("/dashboard/hr-admin/leave-types");
  });

  it("does not send a leave type, leaving the server to provision annual leave", async () => {
    render(
      <EntitlementForm endpoint="/api/v1/entitlements/" method="POST" />
    );

    submitForm();

    await waitFor(() => expect(global.fetch).toHaveBeenCalled());

    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const body = JSON.parse(init.body as string);
    expect(body).toEqual({
      grade_start: "V",
      grade_end: "Z",
      days: 30,
      effective_from: "2026-01-01",
    });
    expect(body).not.toHaveProperty("leave_type");
  });

  it("surfaces the server's message when provisioning annual leave fails", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ name: "Annual leave is created and maintained here." }),
    }) as unknown as typeof fetch;

    render(
      <EntitlementForm endpoint="/api/v1/entitlements/" method="POST" />
    );
    submitForm();

    expect(
      await screen.findByText(/name: Annual leave is created and maintained here/)
    ).toBeInTheDocument();
  });

  it("prefills an existing band and patches it on save", async () => {
    render(
      <EntitlementForm
        entitlement={band}
        endpoint="/api/v1/entitlements/3/"
        method="PATCH"
      />
    );

    expect(screen.getByLabelText("Grade start")).toHaveValue("A");
    expect(screen.getByLabelText("Annual days")).toHaveValue(21);

    fireEvent.change(screen.getByLabelText("Annual days"), {
      target: { value: "23" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("/api/v1/entitlements/3/");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({
      grade_start: "A",
      grade_end: "C",
      days: 23,
      effective_from: "2026-01-01",
    });
  });
});