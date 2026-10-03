"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import type { ApproverRole, ApproverRoleInput } from "@/lib/approver-roles";
import type { HistoryScope } from "@/lib/approver-role-scopes";
import {
  createApproverRole,
  historyScopeLabel,
  HISTORY_SCOPES,
  updateApproverRole,
} from "@/lib/approver-roles-client";

/**
 * Creating a role asks for one thing: its name.
 *
 * The code every rule reads is derived from the name, and the behavioural
 * fields are decisions about who the role is for — history scope, cancellation
 * handling, institution-wide holding — which are better answered once the role
 * exists and its place is understood. Editing then exposes them, and nothing but
 * the name is fixed: a role is quoted by the stages and decisions that used it,
 * so renaming it would make those quote something that no longer exists.
 */
export function ApproverRoleForm({
  role,
  onSuccess,
  onCancel,
}: {
  role?: ApproverRole;
  /**
   * When provided the form reports the saved record instead of navigating, so a
   * dialog can close and refresh its list without the page moving underneath it.
   * Defaults to the push-and-refresh the standalone pages rely on.
   */
  onSuccess?: (role: ApproverRole) => void;
  /** Replaces the Cancel link when the form is hosted in a dialog. */
  onCancel?: () => void;
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(event.currentTarget);
    const input: ApproverRoleInput = {
      label: String(formData.get("label") || ""),
      description: String(formData.get("description") || ""),
      history_scope: String(
        formData.get("history_scope") || "none"
      ) as HistoryScope,
      handles_cancellation: formData.get("handles_cancellation") === "on",
      is_institution_wide: formData.get("is_institution_wide") === "on",
    };

    try {
      const saved = role
        ? // Neither the name nor the derived code is sent on an edit. The name
          // is read-only here and the backend refuses a changed label; the code
          // is the role's identity in saved workflow sections and team
          // memberships. Sending either unchanged would only be a way to earn
          // that refusal by accident.
          await updateApproverRole(role.id, {
            description: input.description,
            history_scope: input.history_scope,
            handles_cancellation: input.handles_cancellation,
            is_institution_wide: input.is_institution_wide,
          })
        : // Creating asks for a name and nothing else, so nothing else is sent:
          // the behavioural fields are absent from the form at this point, and
          // sending their empty defaults would overwrite the ones the backend
          // picked for a role whose scope nobody has decided yet.
          await createApproverRole({ label: input.label });
      if (onSuccess) {
        onSuccess(saved);
      } else {
        router.push("/dashboard/hr-admin/roles");
        router.refresh();
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "An error occurred. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="grid grid-cols-1 gap-4 md:grid-cols-2"
    >
      <div className={role ? "md:col-span-2" : ""}>
        <label
          htmlFor="label"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Name
        </label>
        <input
          id="label"
          name="label"
          required
          maxLength={80}
          readOnly={role !== undefined}
          defaultValue={role?.label}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus read-only:bg-surface-muted read-only:text-text-secondary"
          placeholder="e.g. Head of Department"
        />
        <p className="mt-1 text-xs text-text-muted">
          {role
            ? "A role's name cannot change once it exists: the stages and decisions that used it quote it. Create a new role instead and retire this one."
            : "The code workflow steps store is derived from this name, so there is nothing else to give it."}
        </p>
      </div>

      {role ? (
        <>
          <div className="md:col-span-2">
            <span className="mb-1 block text-sm font-medium text-text-primary">
              Code
            </span>
            <code className="inline-block rounded-md border border-border-default bg-surface-muted px-2 py-1 text-sm text-text-secondary">
              {role.code}
            </code>
            <p className="mt-1 text-xs text-text-muted">
              What workflow steps store and the routing rules read. It cannot
              change.
            </p>
          </div>

          <div className="md:col-span-2">
            <label
              htmlFor="description"
              className="mb-1 block text-sm font-medium text-text-primary"
            >
              Description
            </label>
            <input
              id="description"
              name="description"
              maxLength={255}
              defaultValue={role.description}
              className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
              placeholder="What this approver is responsible for"
            />
          </div>

          <div className="md:col-span-2">
            <label
              htmlFor="history_scope"
              className="mb-1 block text-sm font-medium text-text-primary"
            >
              Leave history visible to this approver
            </label>
            <select
              id="history_scope"
              name="history_scope"
              defaultValue={role.history_scope ?? "none"}
              className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
            >
              {HISTORY_SCOPES.map((scope) => (
                <option key={scope} value={scope}>
                  {historyScopeLabel(scope)}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-text-muted">
              How much of an applicant&apos;s leave history this role sees when
              deciding. It is narrowed further when the applicant is outside the
              approver&apos;s own team.
            </p>
          </div>

          <label className="flex items-start gap-2 md:col-span-2">
            <input
              type="checkbox"
              name="is_institution_wide"
              defaultChecked={role.is_institution_wide}
              className="mt-0.5 size-4 rounded border-input-border text-brand-primary focus:ring-input-ring-focus"
            />
            <span>
              <span className="block text-sm font-medium text-text-primary">
                Institution-wide role
              </span>
              <span className="block text-xs text-text-muted">
                One holder covers every application, so this role is not staffed
                team by team. Use it for a single Registrar, not a Head of
                Department.
              </span>
            </span>
          </label>

          <label className="flex items-start gap-2 md:col-span-2">
            <input
              type="checkbox"
              name="handles_cancellation"
              defaultChecked={role.handles_cancellation}
              className="mt-0.5 size-4 rounded border-input-border text-brand-primary focus:ring-input-ring-focus"
            />
            <span>
              <span className="block text-sm font-medium text-text-primary">
                Decides cancellations
              </span>
              <span className="block text-xs text-text-muted">
                This role can approve or reject a cancellation request. Every
                institution should have at least one such role.
              </span>
            </span>
          </label>
        </>
      ) : null}

      {error && (
        <div className="rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected md:col-span-2">
          {error}
        </div>
      )}

      <div className="flex items-center gap-3 md:col-span-2">
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-button-primary px-4 py-2 font-medium text-button-primary-foreground hover:bg-button-primary-hover focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Saving..." : role ? "Save changes" : "Create role"}
        </button>
        {onCancel ? (
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-text-secondary hover:bg-button-secondary-hover"
          >
            Cancel
          </button>
        ) : (
          <Link
            href="/dashboard/hr-admin/roles"
            className="rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-text-secondary hover:bg-button-secondary-hover"
          >
            Cancel
          </Link>
        )}
      </div>
    </form>
  );
}