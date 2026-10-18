"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import type { Campus, CampusInput } from "@/lib/teams";
import { createCampus, updateCampus } from "@/lib/teams-client";

/**
 * One campus, written.
 *
 * Used for both a new campus and an edit of an existing one: the shape of the
 * thing being written does not change when it is written a second time, and a
 * second form would only be a place for the two to drift apart. On edit the
 * code stays editable for as long as no team uses the campus — a team stores
 * the campus's id, so renaming it here is one write rather than one per team.
 */
export function CampusForm({
  campus,
  onSaved,
  returnTo = "/organisation/campuses",
}: {
  campus?: Campus | null;
  /** Called after a successful save, in place of navigating away. */
  onSaved?: () => void;
  /** Where to go after saving. Empty stays on the page that was open. */
  returnTo?: string;
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const editing = Boolean(campus);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(event.currentTarget);
    const input: CampusInput = {
      name: String(formData.get("name") || ""),
      code: String(formData.get("code") || ""),
      description: String(formData.get("description") || ""),
    };

    try {
      if (editing && campus) {
        await updateCampus(campus.id, input);
      } else {
        await createCampus(input);
      }
      onSaved?.();
      if (returnTo) {
        router.push(returnTo);
      }
      router.refresh();
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
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label
          htmlFor="campus_name"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Name
        </label>
        <input
          id="campus_name"
          name="name"
          required
          defaultValue={campus?.name ?? ""}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          placeholder="e.g. Main Campus"
        />
      </div>
      <div>
        <label
          htmlFor="campus_code"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Code
        </label>
        <input
          id="campus_code"
          name="code"
          required
          defaultValue={campus?.code ?? ""}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          placeholder="e.g. main"
        />
        <p className="mt-1 text-xs text-text-muted">
          A short, stable identifier. Teams that sit at this campus keep working
          if the name changes later.
        </p>
      </div>
      <div>
        <label
          htmlFor="campus_description"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Description
        </label>
        <input
          id="campus_description"
          name="description"
          defaultValue={campus?.description ?? ""}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          placeholder="Where this campus sits"
        />
      </div>
      {error && <p className="text-sm text-status-rejected">{error}</p>}
      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-button-primary px-3 py-1.5 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Saving..." : editing ? "Save campus" : "Create campus"}
        </button>
        <button
          type="button"
          onClick={() => {
            if (onSaved) {
              onSaved();
              return;
            }
            router.push(returnTo);
          }}
          className="rounded-md border border-border-default bg-button-secondary px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

/**
 * The campus list, with the form one click away.
 *
 * Kept on the teams page because that is where a campus is usually first
 * needed — "this team sits at a campus" is the question, and the campus not
 * existing is the answer that stops the form. The full list lives on the
 * Campuses page, which is where a campus is edited once teams already use it.
 */
export function CampusQuickAdd({ campuses }: { campuses: Campus[] }) {
  const [open, setOpen] = useState(false);

  if (!open) {
    return (
      <div>
        {campuses.length === 0 ? (
          <p className="text-sm text-text-muted">
            No campuses yet. A campus is required for an academic team.
          </p>
        ) : (
          <ul className="space-y-1 text-sm text-text-secondary">
            {campuses.map((campus) => (
              <li key={campus.id}>
                <a
                  href={`/organisation/campuses/${campus.id}`}
                  className="font-medium text-brand-primary hover:text-brand-primary-hover"
                >
                  {campus.name}
                </a>{" "}
                <span className="font-mono text-xs text-text-muted">
                  {campus.code}
                </span>
              </li>
            ))}
          </ul>
        )}
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="mt-3 rounded-md border border-border-default bg-button-secondary px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
        >
          Add a campus
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <CampusForm onSaved={() => setOpen(false)} returnTo="" />
      <button
        type="button"
        onClick={() => setOpen(false)}
        className="rounded-md border border-border-default bg-button-secondary px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
      >
        Cancel
      </button>
    </div>
  );
}
