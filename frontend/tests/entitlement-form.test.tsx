import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EntitlementForm } from "@/components/hr/entitlement-form";
import type { Entitlement } from "@/lib/entitlements";

import { pickDate } from "./helpers/date";

const band: Entitlement = {
  id: 3,
  grade_start: "A",
  grade_end: "C",
  days: 21,
  effective_from: "2026-01-01",
  leave_type: 1,
  leave_type_name: "Annual Leave",
};

/** The entitlement endpoint call, skipping the leave-type list read on mount. */
function entitlementCall() {
  return (global.fetch as ReturnType<typeof vi.fn>).mock.calls.find(
    ([url]) => !String(url).includes("leave-config")
  );
}

function stubFetch(
  response: unknown = band,
  ok = true
) {
  global.fetch = vi.fn(async (input: RequestInfo | URL) => {
    if (String(input).includes("leave-config")) {
      // The registry endpoint answers with a bare array, not a page envelope.
      return { ok: true, json: async () => [] };
    }
    return { ok, json: async () => response };
  }) as unknown as typeof fetch;
}

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
  pickDate(screen.getByLabelText("Effective from"), "2026-01-01");
}

function submitForm() {
  fillForm();
  fireEvent.click(screen.getByRole("button", { name: /entitlement/i }));
}

describe("EntitlementForm", () => {
  beforeEach(() => {
    stubFetch();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("offers the grade band fields and a leave-type picker", () => {
    render(
      <EntitlementForm endpoint="/api/v1/entitlements/" method="POST" />
    );

    expect(screen.getByLabelText("Grade start")).toBeInTheDocument();
    expect(screen.getByLabelText("Grade end")).toBeInTheDocument();
    expect(screen.getByLabelText("Annual days")).toBeInTheDocument();
    expect(screen.getByLabelText("Effective from")).toBeInTheDocument();
    expect(screen.getByLabelText("Leave type")).toBeInTheDocument();
  });

  it("says annual leave is provisioned for the band", () => {
    render(
      <EntitlementForm endpoint="/api/v1/entitlements/" method="POST" />
    );

    expect(
      screen.getByText(/Annual Leave is created for you/)
    ).toBeInTheDocument();
  });

  it("sends null when the band is left on annual leave", async () => {
    render(
      <EntitlementForm endpoint="/api/v1/entitlements/" method="POST" />
    );

    submitForm();

    await waitFor(() => expect(entitlementCall()).toBeTruthy());

    const [, init] = entitlementCall()!;
    const body = JSON.parse(init.body as string);
    expect(body).toEqual({
      grade_start: "V",
      grade_end: "Z",
      days: 30,
      effective_from: "2026-01-01",
      leave_type: null,
    });
  });

  it("surfaces the server's message when provisioning fails", async () => {
    stubFetch({ name: "Annual leave is created and maintained here." }, false);

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

    await waitFor(() => expect(entitlementCall()).toBeTruthy());
    const [url, init] = entitlementCall()!;
    expect(url).toBe("/api/v1/entitlements/3/");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({
      grade_start: "A",
      grade_end: "C",
      days: 23,
      effective_from: "2026-01-01",
      leave_type: 1,
    });
  });
});
