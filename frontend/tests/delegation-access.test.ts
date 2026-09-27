import { describe, expect, it } from "vitest";

import { canRequestCover } from "@/lib/delegations";

describe("canRequestCover", () => {
  it("allows every role the backend treats as an approver", () => {
    for (const role of [
      "supervisor",
      "hod",
      "dean",
      "registrar",
      "dvc",
      "hr",
    ]) {
      expect(canRequestCover(role)).toBe(true);
    }
  });

  it("rejects a plain employee and any missing role", () => {
    expect(canRequestCover("employee")).toBe(false);
    expect(canRequestCover("")).toBe(false);
    expect(canRequestCover(null)).toBe(false);
    expect(canRequestCover(undefined)).toBe(false);
  });
});
