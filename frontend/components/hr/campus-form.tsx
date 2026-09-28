"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import type { Campus, CampusInput } from "@/lib/teams";
import { createCampus } from "@/lib/teams-client";

/** Reference data: campuses HR maintains to scope teams. */
export function CampusForm({ campuses }: { campuses: Campus[] }) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

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
      await createCampus(input);
      setOpen(false);
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

  if (!open) {
    return (
      <div>
        {campuses.length === 0 ? (
          <p className="text-sm text-text-muted">
            No campuses yet. A campus is optional on a team.
          </p>
        ) : (
          <ul className="space-y-1 text-sm text-text-secondary">
            {campuses.map((campus) => (
              <li key={campus.id}>
                {campus.name}{" "}
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
    <form onSubmit={handleSubmit} className="space-y-3">
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
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          placeholder="e.g. main"
        />
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
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          placeholder="Where this campus sits"
        />
      </div>
      {error && (
        <p className="text-sm text-status-rejected">{error}</p>
      )}
      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-button-primary px-3 py-1.5 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Saving..." : "Create campus"}
        </button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="rounded-md border border-border-default bg-button-secondary px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
