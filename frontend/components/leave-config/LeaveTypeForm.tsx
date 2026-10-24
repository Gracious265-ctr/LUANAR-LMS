"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  BRANCH_SCOPE_OPTIONS,
  GENDER_OPTIONS,
  LEAVE_TYPE_COLORS,
  draftToInput,
  emptyLeaveTypeDraft,
  isAnnualLeaveType,
  leaveTypeFieldErrors,
  leaveTypeFormError,
  leaveTypeToDraft,
  validateLeaveTypeDraft,
  type BranchScope,
  type GenderEligibility,
  type GradeOption,
  type LeaveType,
  type LeaveTypeDraft,
  type LeaveTypeFieldErrors,
} from "@/lib/leave-config";
import {
  LeaveConfigRequestError,
  createLeaveType,
  listGrades,
  updateLeaveType,
} from "@/lib/leave-config-client";
import { Alert } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, Input } from "@/components/ui/input";
import { FormError } from "@/components/ui/form-error";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Stepper, type Step } from "@/components/ui/Stepper";
import { Textarea } from "@/components/ui/textarea";

import { DeactivateDialog } from "./DeactivateDialog";

const STEP_IDS = ["basics", "eligibility", "rules"] as const;
type StepId = (typeof STEP_IDS)[number];

/** Which step mounts each field the API can complain about. */
const STEP_OF_FIELD: Record<keyof LeaveTypeFieldErrors, StepId> = {
  name: "basics",
  code: "basics",
  max_duration_days: "rules",
  notice_days: "rules",
};

/** The earliest step that owns one of the errored fields, if any. */
function firstStepWithError(errors: LeaveTypeFieldErrors): StepId | null {
  for (const stepId of STEP_IDS) {
    const owns = (Object.keys(errors) as (keyof LeaveTypeFieldErrors)[]).some(
      (field) => STEP_OF_FIELD[field] === stepId
    );
    if (owns) {
      return stepId;
    }
  }
  return null;
}

/**
 * One form for both create and edit (spec 3.3) — 3-step form using Stepper,
 * matching the Leave app multi-step pattern.
 */
export function LeaveTypeForm({ leaveType }: { leaveType?: LeaveType }) {
  const router = useRouter();

  const [draft, setDraft] = useState<LeaveTypeDraft>(() =>
    leaveType ? leaveTypeToDraft(leaveType) : emptyLeaveTypeDraft()
  );
  const [fieldErrors, setFieldErrors] = useState<LeaveTypeFieldErrors>({});
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);

  const [currentStep, setCurrentStep] = useState<StepId>("basics");
  const [reachedSteps, setReachedSteps] = useState<Set<StepId>>(
    new Set(["basics"])
  );

  const [grades, setGrades] = useState<GradeOption[]>([]);
  const [gradesError, setGradesError] = useState("");
  useEffect(() => {
    listGrades()
      .then((data) => {
        setGrades(data);
        setGradesError("");
      })
      .catch(() => {
        setGradesError("Could not load grades from the directory.");
      });
  }, []);

  const patch = (next: Partial<LeaveTypeDraft>) => {
    setDraft((current) => ({ ...current, ...next }));
    setFieldErrors((current) => {
      const cleared = { ...current };
      for (const key of Object.keys(next)) {
        delete cleared[key as keyof LeaveTypeFieldErrors];
      }
      return cleared;
    });
  };

  const gradeOptions: GradeOption[] = [
    ...grades,
    ...draft.eligible_grades
      .filter((id) => !grades.some((grade) => grade.id === id))
      .map((id) => ({ id, name: id })),
  ];

  const isAnnual = Boolean(leaveType && isAnnualLeaveType(leaveType));
  const showRegistrar = draft.branch_scope !== "academic";

  const validateStep = (stepId: StepId): boolean => {
    if (stepId === "basics") {
      const errors = validateLeaveTypeDraft(draft);
      const basicsErrors: LeaveTypeFieldErrors = {};
      if (errors.name) basicsErrors.name = errors.name;
      if (errors.code) basicsErrors.code = errors.code;
      setFieldErrors((current) => ({ ...current, ...basicsErrors }));
      return !basicsErrors.name && !basicsErrors.code;
    }
    if (stepId === "eligibility") {
      setFieldErrors((current) => ({ ...current }));
      return true;
    }
    if (stepId === "rules") {
      const errors = validateLeaveTypeDraft(draft);
      setFieldErrors(errors);
      return Object.keys(errors).length === 0;
    }
    return true;
  };

  const goToStep = (stepId: StepId) => {
    if (stepId === currentStep) return;
    if (!reachedSteps.has(stepId)) return;
    setCurrentStep(stepId);
  };

  const handleNext = () => {
    if (!validateStep(currentStep)) return;
    if (currentStep === "basics") {
      const nextReached = new Set(reachedSteps);
      nextReached.add("eligibility");
      setReachedSteps(nextReached);
      setCurrentStep("eligibility");
    } else if (currentStep === "eligibility") {
      const nextReached = new Set(reachedSteps);
      nextReached.add("rules");
      setReachedSteps(nextReached);
      setCurrentStep("rules");
    }
  };

  const handleBack = () => {
    if (currentStep === "eligibility") {
      setCurrentStep("basics");
    } else if (currentStep === "rules") {
      setCurrentStep("eligibility");
    }
  };

  const steps: Step[] = useMemo(() => {
    const getStatus = (stepId: StepId) => {
      if (currentStep === stepId) return "current" as const;
      if (reachedSteps.has(stepId)) return "completed" as const;
      return "pending" as const;
    };

    return [
      {
        id: "basics",
        label: "Basics",
        status: getStatus("basics"),
      },
      {
        id: "eligibility",
        label: "Eligibility",
        status: getStatus("eligibility"),
      },
      {
        id: "rules",
        label: "Rules",
        status: getStatus("rules"),
      },
    ];
  }, [currentStep, reachedSteps]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (currentStep !== "rules") {
      return;
    }

    if (!validateStep("rules")) return;

    const errors = validateLeaveTypeDraft(draft);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) {
      setFormError("");
      return;
    }

    setSaving(true);
    setFormError("");
    try {
      const input = draftToInput(draft);
      if (leaveType) {
        await updateLeaveType(leaveType.id, input);
      } else {
        await createLeaveType(input);
      }
      router.push("/leave-config");
      router.refresh();
    } catch (err) {
      if (err instanceof LeaveConfigRequestError) {
        const errors = leaveTypeFieldErrors(err.data);
        setFieldErrors(errors);
        setFormError(
          leaveTypeFormError(err.data) ||
            (Object.keys(errors).length > 0 ? "" : err.message)
        );
        // A field error is only useful where its field is mounted. Move the
        // reader to the earliest step that owns one, so the message is on
        // screen instead of on a step they cannot see.
        const erroredStep = firstStepWithError(errors);
        if (erroredStep) {
          setReachedSteps((current) => {
            const next = new Set(current);
            for (const id of STEP_IDS) {
              next.add(id);
              if (id === erroredStep) break;
            }
            return next;
          });
          setCurrentStep(erroredStep);
        }
      } else {
        setFormError(
          err instanceof Error ? err.message : "Something went wrong. Please try again."
        );
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <form onSubmit={handleSubmit} className="space-y-8">
        {leaveType && !leaveType.is_active && (
          <Alert tone="info">
            This leave type is inactive, so employees cannot select it for new
            applications or plans. Everything already filed against it is
            untouched.
          </Alert>
        )}

        {isAnnual && (
          <Alert tone="info">
            <p>
              {leaveType?.name} is created for you the first time you add an
              entitlement, so its name and short code are fixed. Its rules are
              yours to change here; how many days a grade range is granted is
              changed by editing{" "}
              <Link
                href="/dashboard/hr-admin/entitlements"
                className="font-medium underline"
              >
                the entitlement
              </Link>
              .
            </p>
          </Alert>
        )}

        <div className="space-y-6">
          <div className="pb-4 border-b border-border-default">
            <Stepper
              steps={steps}
              orientation="horizontal"
              activeStep={["basics", "eligibility", "rules"].indexOf(currentStep)}
              interactive={false}
            />
          </div>

          {currentStep === "basics" && (
            <section className="space-y-4">
              <h4 className="text-base font-semibold text-text-primary">Basics</h4>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <Field
                  label="Name"
                  htmlFor="name"
                  error={fieldErrors.name ?? null}
                  hint={
                    isAnnual
                      ? "Fixed: annual leave is created by an entitlement."
                      : undefined
                  }
                >
                  <Input
                    id="name"
                    name="name"
                    required
                    readOnly={isAnnual}
                    value={draft.name}
                    onChange={(event) => patch({ name: event.target.value })}
                    placeholder="e.g. Study leave"
                    aria-invalid={fieldErrors.name ? true : undefined}
                  />
                </Field>

                <Field
                  label="Short code"
                  htmlFor="code"
                  hint={
                    isAnnual
                      ? "Fixed: annual leave is found by its short code."
                      : "Leave blank to derive it from the name. The codes annual and annual-leave are reserved."
                  }
                  error={fieldErrors.code ?? null}
                >
                  <Input
                    id="code"
                    name="code"
                    readOnly={isAnnual}
                    value={draft.code}
                    onChange={(event) => patch({ code: event.target.value })}
                    placeholder="Optional; derived from name"
                    aria-invalid={fieldErrors.code ? true : undefined}
                  />
                </Field>

                <div className="space-y-block">
                  <p
                    id="color-label"
                    className="text-sm font-medium leading-none text-text-secondary"
                  >
                    Colour
                  </p>
                  <div
                    role="radiogroup"
                    aria-labelledby="color-label"
                    className="flex flex-wrap items-center gap-2"
                  >
                    {LEAVE_TYPE_COLORS.map((option) => (
                      <label
                        key={option.value}
                        htmlFor={`color-${option.value}`}
                        className="cursor-pointer"
                      >
                        <input
                          id={`color-${option.value}`}
                          type="radio"
                          name="color"
                          value={option.value}
                          checked={draft.color === option.value}
                          onChange={() => patch({ color: option.value })}
                          className="peer sr-only"
                        />
                        <span
                          className="block size-7 rounded-md border border-border-default transition-shadow peer-checked:ring-2 peer-checked:ring-brand-primary peer-checked:ring-offset-2 peer-focus-visible:ring-2 peer-focus-visible:ring-brand-primary"
                          style={{ backgroundColor: option.hex }}
                        />
                        <span className="sr-only">{option.label}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <Field
                  label="Description"
                  htmlFor="description"
                  hint="Shown to employees as help text when they pick this type."
                >
                  <Textarea
                    id="description"
                    name="description"
                    rows={3}
                    value={draft.description}
                    onChange={(event) => patch({ description: event.target.value })}
                  />
                </Field>
              </div>
            </section>
          )}

          {currentStep === "eligibility" && (
            <section className="space-y-4">
              <h4 className="text-base font-semibold text-text-primary">Eligibility</h4>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <Field
                  label="Branch scope"
                  htmlFor="branch_scope"
                  hint="Which arm of the institution this type applies to."
                >
                  <Select
                    value={draft.branch_scope}
                    onValueChange={(value) => patch({ branch_scope: value as BranchScope })}
                  >
                    <SelectTrigger id="branch_scope" aria-label="Branch scope">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {BRANCH_SCOPE_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>

                <Field
                  label="Eligible gender"
                  htmlFor="eligible_gender"
                  hint="Leave types such as maternity or paternity leave restrict this."
                >
                  <Select
                    value={draft.eligible_gender}
                    onValueChange={(value) =>
                      patch({ eligible_gender: value as GenderEligibility })
                    }
                  >
                    <SelectTrigger id="eligible_gender" aria-label="Eligible gender">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {GENDER_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>

                <div className="space-y-2 md:col-span-2">
                  <p
                    id="eligible-grades-label"
                    className="text-sm font-medium leading-none text-text-secondary"
                  >
                    Eligible grades
                  </p>
                  <p className="text-xs text-text-muted">
                    Tick the grades this type is limited to. Leave all of them
                    unticked to allow every grade.
                  </p>
                  <div
                    role="group"
                    aria-labelledby="eligible-grades-label"
                    className="flex flex-wrap gap-x-5 gap-y-2"
                  >
                    {gradeOptions.length === 0 && (
                      <p className="text-sm text-text-muted">No grades available.</p>
                    )}
                    {gradeOptions.map((grade) => (
                      <label
                        key={grade.id}
                        htmlFor={`grade-${grade.id}`}
                        className="inline-flex cursor-pointer items-center gap-2 text-sm text-text-primary"
                      >
                        <Checkbox
                          id={`grade-${grade.id}`}
                          checked={draft.eligible_grades.includes(grade.id)}
                          onCheckedChange={(next) =>
                            patch({
                              eligible_grades: next === true
                                ? [...draft.eligible_grades, grade.id]
                                : draft.eligible_grades.filter((id) => id !== grade.id),
                            })
                          }
                        />
                        {grade.name}
                      </label>
                    ))}
                  </div>
                  {gradesError && (
                    <p className="text-xs text-text-muted">{gradesError}</p>
                  )}
                </div>
              </div>
            </section>
          )}

          {currentStep === "rules" && (
            <section className="space-y-4">
              <h4 className="text-base font-semibold text-text-primary">Rules</h4>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <Field
                  label="Maximum duration (days)"
                  htmlFor="max_duration_days"
                  hint="Longest single application. Leave blank for no maximum."
                  error={fieldErrors.max_duration_days ?? null}
                >
                  <Input
                    id="max_duration_days"
                    name="max_duration_days"
                    type="number"
                    step="any"
                    value={draft.max_duration_days}
                    onChange={(event) => patch({ max_duration_days: event.target.value })}
                    placeholder="e.g. 21"
                    aria-invalid={fieldErrors.max_duration_days ? true : undefined}
                  />
                </Field>

                <Field
                  label="Notice period (days)"
                  htmlFor="notice_days"
                  hint="Advance notice this type requires. It also sets how far ahead the Leave Plans reminder fires. Leave blank for no minimum."
                  error={fieldErrors.notice_days ?? null}
                >
                  <Input
                    id="notice_days"
                    name="notice_days"
                    type="number"
                    step="any"
                    value={draft.notice_days}
                    onChange={(event) => patch({ notice_days: event.target.value })}
                    placeholder="e.g. 14"
                    aria-invalid={fieldErrors.notice_days ? true : undefined}
                  />
                </Field>

                <div className="md:col-span-2">
                  <label
                    htmlFor="requires_supporting_document"
                    className="inline-flex cursor-pointer items-center gap-2 text-sm font-medium text-text-primary"
                  >
                    <Checkbox
                      id="requires_supporting_document"
                      checked={draft.requires_supporting_document}
                      onCheckedChange={(next) =>
                        patch({ requires_supporting_document: next === true })
                      }
                    />
                    Requires a supporting document
                  </label>
                </div>

                <div className="md:col-span-2 space-y-4">
                  <h4 className="text-base font-semibold text-text-primary">Planning</h4>
                  <label
                    htmlFor="plannable"
                    className="inline-flex cursor-pointer items-center gap-2 text-sm font-medium text-text-primary"
                  >
                    <Checkbox
                      id="plannable"
                      checked={draft.plannable}
                      onCheckedChange={(next) => patch({ plannable: next === true })}
                    />
                    Plannable — employees can schedule this type as a Leave Plan
                  </label>
                </div>

                {showRegistrar && (
                  <div className="md:col-span-2 space-y-4">
                    <h4 className="text-base font-semibold text-text-primary">Approval</h4>
                    <label
                      htmlFor="requires_institutional_registrar_approval"
                      className="inline-flex cursor-pointer items-center gap-2 text-sm font-medium text-text-primary"
                    >
                      <Checkbox
                        id="requires_institutional_registrar_approval"
                        checked={draft.requires_institutional_registrar_approval}
                        onCheckedChange={(next) =>
                          patch({ requires_institutional_registrar_approval: next === true })
                        }
                      />
                      Requires Institutional Registrar approval
                    </label>
                  </div>
                )}
              </div>
            </section>
          )}
        </div>

        {formError && <FormError>{formError}</FormError>}

        <div className="flex flex-wrap items-center gap-3 border-t border-border-default pt-5">
          {leaveType && !isAnnual && (
            <Button
              type="button"
              variant="secondary"
              className="mr-auto"
              onClick={() => setDialogOpen(true)}
            >
              {leaveType.is_active ? "Deactivate" : "Reactivate"}
            </Button>
          )}
          {currentStep !== "basics" && (
            <Button type="button" variant="secondary" onClick={handleBack}>
              Back
            </Button>
          )}
          {currentStep !== "rules" ? (
            <Button key="next" type="button" variant="primary" onClick={handleNext}>
              Next
            </Button>
          ) : (
            <Button key="submit" type="submit" variant="primary" loading={saving}>
              {saving ? "Saving…" : leaveType ? "Save changes" : "Create leave type"}
            </Button>
          )}
          <Link href="/leave-config" className={buttonVariants({ variant: "secondary" })}>
            Cancel
          </Link>
        </div>
      </form>

      {leaveType && !isAnnual && (
        <DeactivateDialog
          leaveType={leaveType}
          open={dialogOpen}
          onOpenChange={setDialogOpen}
          onToggled={() => {
            setDialogOpen(false);
            router.refresh();
          }}
        />
      )}
    </Card>
  );
}
