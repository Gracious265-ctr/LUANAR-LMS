import { describe, expect, it } from "vitest";

import {
  ANNUAL_LEAVE_CODES,
  branchScopeLabel,
  colorHex,
  dayCountLabel,
  draftToInput,
  emptyLeaveTypeDraft,
  genderLabel,
  isAnnualLeaveType,
  leaveTypeFieldErrors,
  leaveTypeFormError,
  leaveTypeToDraft,
  validateLeaveTypeDraft,
  type LeaveType,
  type LeaveTypeDraft,
} from "@/lib/leave-config";
import {
  LEAVE_CONFIG_NAV_ITEMS,
  isLeaveConfigModule,
} from "@/lib/nav/leave-config-nav";

function draft(overrides: Partial<LeaveTypeDraft> = {}): LeaveTypeDraft {
  return { ...emptyLeaveTypeDraft(), ...overrides };
}

function leaveType(overrides: Partial<LeaveType> = {}): LeaveType {
  return {
    id: 7,
    name: "Study leave",
    code: "study",
    color: "purple",
    description: "Long study leave",
    branch_scope: "both",
    eligible_grades: ["A", "G"],
    eligible_gender: "any",
    requires_supporting_document: true,
    max_duration_days: 21,
    notice_days: 14,
    eligibility: "",
    eligibility_rules: [],
    consumes_annual_entitlement: false,
    plannable: true,
    requires_institutional_registrar_approval: false,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
    ...overrides,
  };
}

describe("leave type draft validation (spec 3.3)", () => {
  it("requires a name", () => {
    expect(validateLeaveTypeDraft(draft({ name: "   " })).name).toBe(
      "Name is required."
    );
    expect(validateLeaveTypeDraft(draft({ name: "Study leave" })).name).toBeUndefined();
  });

  it("rejects a negative maximum duration", () => {
    const errors = validateLeaveTypeDraft(
      draft({ name: "Study leave", max_duration_days: "-3" })
    );
    expect(errors.max_duration_days).toBe(
      "Maximum duration must be a whole number of at least 1 day."
    );
  });

  it("rejects a maximum duration of zero, since it is not a positive length", () => {
    const errors = validateLeaveTypeDraft(
      draft({ name: "Study leave", max_duration_days: "0" })
    );
    expect(errors.max_duration_days).toBeDefined();
  });

  it("rejects a fractional maximum duration", () => {
    const errors = validateLeaveTypeDraft(
      draft({ name: "Study leave", max_duration_days: "2.5" })
    );
    expect(errors.max_duration_days).toBeDefined();
  });

  it("rejects a negative notice period but allows zero notice", () => {
    expect(
      validateLeaveTypeDraft(draft({ name: "Study leave", notice_days: "-1" }))
        .notice_days
    ).toBe("Notice period must be a whole number of days and cannot be negative.");
    expect(
      validateLeaveTypeDraft(draft({ name: "Study leave", notice_days: "0" }))
        .notice_days
    ).toBeUndefined();
  });

  it("allows both numerics to be blank, meaning no limit at all", () => {
    expect(
      validateLeaveTypeDraft(
        draft({ name: "Study leave", max_duration_days: "", notice_days: "" })
      )
    ).toEqual({});
  });
});

describe("draftToInput", () => {
  it("trims what was typed and drops a blank grade rather than sending it", () => {
    const input = draftToInput(
      draft({
        name: "  Study leave  ",
        code: "  ",
        description: "  Long study leave  ",
        eligible_grades: ["A", "  ", "G"],
      })
    );

    expect(input.name).toBe("Study leave");
    expect(input.code).toBeUndefined();
    expect(input.description).toBe("Long study leave");
    expect(input.eligible_grades).toEqual(["A", "G"]);
  });

  it("sends null rather than NaN when a numeric is left blank", () => {
    const input = draftToInput(
      draft({ name: "Study leave", max_duration_days: "", notice_days: "" })
    );
    expect(input.max_duration_days).toBeNull();
    expect(input.notice_days).toBeNull();
  });

  it("keeps the registrar flag even when its control is hidden", () => {
    // An academic type hides the Approval section; hiding it must not clear
    // the stored value, or an edit to an unrelated field would silently
    // rewrite the approval chain.
    const input = draftToInput(
      draft({
        name: "Study leave",
        branch_scope: "academic",
        requires_institutional_registrar_approval: true,
      })
    );
    expect(input.branch_scope).toBe("academic");
    expect(input.requires_institutional_registrar_approval).toBe(true);
  });
});

describe("annual leave recognition", () => {
  it.each(ANNUAL_LEAVE_CODES)("recognises the %s code", (code) => {
    expect(isAnnualLeaveType({ code })).toBe(true);
  });

  it("recognises the code regardless of case or surrounding space", () => {
    expect(isAnnualLeaveType({ code: "  Annual  " })).toBe(true);
  });

  it("leaves every other type alone", () => {
    expect(isAnnualLeaveType({ code: "maternity" })).toBe(false);
    expect(isAnnualLeaveType({ code: "" })).toBe(false);
    expect(isAnnualLeaveType(null)).toBe(false);
    expect(isAnnualLeaveType(undefined)).toBe(false);
  });
});

describe("DRF error mapping", () => {
  it("takes a field error whether it arrives as a string or a list", () => {
    expect(
      leaveTypeFieldErrors({
        name: ["A leave type with this name already exists."],
        code: "This code is reserved.",
      })
    ).toEqual({
      name: "A leave type with this name already exists.",
      code: "This code is reserved.",
    });
  });

  it("leaves keys with nowhere to render for the banner to pick up", () => {
    expect(leaveTypeFieldErrors({ non_field_errors: ["Bad request."] })).toEqual({});
    expect(leaveTypeFormError({ non_field_errors: ["Bad request."] })).toBe(
      "Bad request."
    );
    expect(leaveTypeFormError({ name: ["Taken."] })).toBe("");
  });

  it("is harmless against a body it does not understand", () => {
    expect(leaveTypeFieldErrors(null)).toEqual({});
    expect(leaveTypeFormError("nope")).toBe("");
    expect(leaveTypeFieldErrors("nope")).toEqual({});
  });
});

describe("draft round-tripping", () => {
  it("renders a stored type back into editable strings", () => {
    const stored = leaveType({ max_duration_days: null, notice_days: null });
    const restored = leaveTypeToDraft(stored);

    expect(restored.max_duration_days).toBe("");
    expect(restored.notice_days).toBe("");
    expect(restored.eligible_grades).toEqual(["A", "G"]);
    expect(restored.plannable).toBe(true);
  });
});

describe("list labels", () => {
  it("names a branch scope and a gender the way the form offers them", () => {
    expect(branchScopeLabel("administrative")).toBe("Administrative");
    expect(genderLabel("female")).toBe("Female");
    // An unknown value is echoed rather than blanked: a row must never lose
    // the fact that it has a scope just because the vocabulary moved on.
    expect(branchScopeLabel("museum" as never)).toBe("museum");
  });

  it("counts days singularly and words an absent limit", () => {
    expect(dayCountLabel(21, "No maximum")).toBe("21 days");
    expect(dayCountLabel(1, "No maximum")).toBe("1 day");
    expect(dayCountLabel(null, "No maximum")).toBe("No maximum");
  });

  it("falls back to the default swatch for a colour it does not know", () => {
    expect(colorHex("purple")).toBe("#9333ea");
    expect(colorHex("chartreuse")).toBe("#2563eb");
  });
});

describe("module rail (spec 3.5)", () => {
  it("scopes every path under /leave-config to the module", () => {
    expect(isLeaveConfigModule("/leave-config")).toBe(true);
    expect(isLeaveConfigModule("/leave-config/new")).toBe(true);
    expect(isLeaveConfigModule("/leave-config/7")).toBe(true);
    expect(isLeaveConfigModule("/dashboard/leave-config")).toBe(false);
    expect(isLeaveConfigModule("/dashboard/leave")).toBe(false);
  });

  it("offers exactly the two destinations the spec lists", () => {
    expect(
      LEAVE_CONFIG_NAV_ITEMS.map((item) => [item.label, item.href])
    ).toEqual([
      ["Leave Types", "/leave-config"],
      ["Create Leave Type", "/leave-config/new"],
    ]);
  });

  it("lights Leave Types on the list and on a single type's form", () => {
    const [leaveTypes] = LEAVE_CONFIG_NAV_ITEMS;
    expect(leaveTypes.match("/leave-config")).toBe(true);
    expect(leaveTypes.match("/leave-config/7")).toBe(true);
    expect(leaveTypes.match("/leave-config/new")).toBe(false);
    expect(leaveTypes.match("/dashboard")).toBe(false);
  });

  it("lights Create Leave Type only on the create form", () => {
    const create = LEAVE_CONFIG_NAV_ITEMS[1];
    expect(create.match("/leave-config/new")).toBe(true);
    expect(create.match("/leave-config")).toBe(false);
    expect(create.match("/leave-config/7")).toBe(false);
  });
});
