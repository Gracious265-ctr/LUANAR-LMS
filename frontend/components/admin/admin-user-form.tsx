"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import type { AdminUser } from "@/lib/admin-users";
import { createAdminUser, updateAdminUser } from "@/lib/admin-users-client";

/** Where the standalone form returns to, and what Cancel links back to. */
const LIST_ROUTE = "/dashboard/admin/users";

/**
 * The superuser's HR-account form.
 *
 * It is intentionally the only account form in the product that sets a role,
 * and it can only set one: every account written here is Human Resources. That
 * is the bootstrap path — the superuser is the account a deployment starts with,
 * and HR is the account that then configures the business data. A normal
 * employee is created by HR from the employee directory, never here.
 */
export function AdminUserForm({
  user,
  onSuccess,
  onCancel,
}: {
  user?: AdminUser;
  /**
   * Replaces the default `router.push(listRoute)` + `router.refresh()`. The
   * overlay passes this so it can close itself and refetch; with it omitted the
   * form navigates on its own, which is what a standalone page needs.
   */
  onSuccess?: (saved: AdminUser) => void;
  /** Adds a dismiss action. An inline page form has nothing to dismiss to. */
  onCancel?: () => void;
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  /** Close-and-refresh when hosted, navigate when standalone. */
  function done(saved: AdminUser) {
    if (onSuccess) {
      onSuccess(saved);
      return;
    }
    router.push(LIST_ROUTE);
    router.refresh();
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(event.currentTarget);
    const password = String(formData.get("password") || "");

    try {
      const saved = user
        ? await updateAdminUser(user.id, {
            email: String(formData.get("email") || ""),
            first_name: String(formData.get("first_name") || ""),
            last_name: String(formData.get("last_name") || ""),
            is_active: formData.get("is_active") === "on",
            ...(password ? { password } : {}),
          })
        : await createAdminUser({
            email: String(formData.get("email") || ""),
            first_name: String(formData.get("first_name") || ""),
            last_name: String(formData.get("last_name") || ""),
            password,
          });
      done(saved);
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
      <div className="md:col-span-2">
        <label
          htmlFor="email"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Email
        </label>
        <input
          id="email"
          name="email"
          type="email"
          required
          readOnly={user !== undefined}
          defaultValue={user?.email}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus read-only:bg-surface-muted read-only:text-text-secondary"
          placeholder="name@luanar.ac.mw"
        />
        <p className="mt-1 text-xs text-text-muted">
          {user
            ? "The sign-in address cannot change once the account exists."
            : "This is also the username. The account signs in with it."}
        </p>
      </div>

      <div>
        <label
          htmlFor="first_name"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          First name
        </label>
        <input
          id="first_name"
          name="first_name"
          defaultValue={user?.first_name}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
      </div>

      <div>
        <label
          htmlFor="last_name"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Last name
        </label>
        <input
          id="last_name"
          name="last_name"
          defaultValue={user?.last_name}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
      </div>

      <div className="md:col-span-2">
        <label
          htmlFor="password"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          {user ? "New password" : "Initial password"}
        </label>
        <input
          id="password"
          name="password"
          type="password"
          required={user === undefined}
          minLength={8}
          autoComplete="new-password"
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          placeholder={user ? "Leave blank to keep the current password" : "At least 8 characters"}
        />
        <p className="mt-1 text-xs text-text-muted">
          HR is the source of credentials. There is no self-service password
          change, so this is how an HR user gets (or regains) access.
        </p>
      </div>

      {user ? (
        <label className="flex items-start gap-2 md:col-span-2">
          <input
            type="checkbox"
            name="is_active"
            defaultChecked={user.is_active}
            className="mt-0.5 size-4 rounded border-input-border text-brand-primary focus:ring-input-ring-focus"
          />
          <span>
            <span className="block text-sm font-medium text-text-primary">
              Active
            </span>
            <span className="block text-xs text-text-muted">
              A deactivated HR account cannot sign in.
            </span>
          </span>
        </label>
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
          {loading ? "Saving..." : user ? "Save changes" : "Create HR user"}
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
            href={LIST_ROUTE}
            className="rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-text-secondary hover:bg-button-secondary-hover"
          >
            Cancel
          </Link>
        )}
      </div>
    </form>
  );
}
