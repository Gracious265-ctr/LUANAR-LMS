import { NextResponse } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/app/api/_lib/api-fetch", () => ({
  apiFetch: (...args: [string, string]) => mockedApiFetch(...args),
}));

import { GET as launcher } from "@/app/api/apps/launcher/route";

const mockedApiFetch = vi.fn<(...args: [string, string]) => Promise<NextResponse>>(
  async () => NextResponse.json({ apps: [] })
);

describe("launcher proxy route", () => {
  beforeEach(() => {
    mockedApiFetch.mockClear();
  });

  it("forwards to the backend apps/launcher endpoint", async () => {
    await launcher();

    // Must match the registered backend path (`/api/v1/apps/launcher/`); a
    // mismatch here silently leaves the launcher grid empty for every role.
    expect(mockedApiFetch).toHaveBeenCalledWith("GET", "apps/launcher/");
  });
});
