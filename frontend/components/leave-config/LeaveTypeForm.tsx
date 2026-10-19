"use client";

import { FormEvent, useEffect, useState } from "react";
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
import { Textarea } from "@/components/ui/textarea";

import { DeactivateDialog } from "./DeactivateDialog";

/**
 * One form for both create and edit (spec 3.3) — five sections, no entitlement
 * field anywhere on it.
 *
 * Per §1.3 the days-per-year number does not exist on a leave type: it is
 * grade-based and configured in Entitlements, so this form has no control that
 * could be mistaken for it.
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

  const [grades, setGrades] = useState<GradeOption[]>([]);
  const [gradesError, setGradesError] = useState("");
  useEffect(() => {
    listGrades()
      .then(setGrades)
      .catch(() =>
        setGradesError(
          "Grades could not be loaded. Any grades already on this type are shown and kept."
        )
      );
  }, []);

  function patch(next: Partial<LeaveTypeDraft>) {
    setDraft((current) => ({ ...current, ...next }));
    setFieldErrors((current) => {
      const cleared = { ...current };
      for (const key of Object.keys(next)) {
        delete cleared[key as keyof LeaveTypeFieldErrors];
      }
      return cleared;
    });
  }

  // A grade the directory no longer answers for must not silently vanish from
  // the type just because it is missing from the option list.
  const gradeOptions: GradeOption[] = [
    ...grades,
    ...draft.eligible_grades
      .filter((id) => !grades.some((grade) => grade.id === id))
      .map((id) => ({ id, name: id })),
  ];

  // Annual leave is provisioned by an entitlement, so its identity is the
  // entitlement's business: the API pins the name and code and refuses to
  // deactivate it. Its *rules*, however, are HR's — this form is the only
  // surface that owns them since the Leave Rules screens were retired.
  const isAnnual = Boolean(leaveType && isAnnualLeaveType(leaveType));

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

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
      } else {
        setFormError(
          err instanceof Error ? err.message : "Something went wrong. Please try again."
        );
      }
    } finally {
      setSaving(false);
    }
  }

  const showRegistrar = draft.branch_scope !== "academic";

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

        <section className="space-y-4">
          <h3 className="text-base font-semibold text-text-primary">Basics</h3>
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

            {/* Not a `Field`: the control is a group of eight swatches, so the
                name is attached to the group rather than to one of them. */}
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

        <section className="space-y-4">
          <h3 className="text-base font-semibold text-text-primary">Eligibility</h3>
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

        <section className="space-y-4">
          <h3 className="text-base font-semibold text-text-primary">Rules</h3>
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
          </div>
        </section>

        <section className="space-y-4">
          <h3 className="text-base font-semibold text-text-primary">Planning</h3>
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
        </section>

        {/* §3.3: meaningless for a purely Academic-scoped type, whose chain
            never reaches the Institutional Registrar regardless of the flag. */}
        {showRegistrar && (
          <section className="space-y-4">
            <h3 className="text-base font-semibold text-text-primary">Approval</h3>
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
          </section>
        )}

        {formError && <FormError>{formError}</FormError>}

        <div className="flex flex-wrap items-center gap-3 border-t border-border-default pt-5">
          {/* Annual leave has no lifecycle here: the API refuses to retire it,
              because every employee must keep selecting it. */}
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
          <Button type="submit" variant="primary" loading={saving}>
            {saving ? "Saving…" : leaveType ? "Save changes" : "Create leave type"}
          </Button>
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
