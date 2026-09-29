"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import type { Campus, Team, TeamInput } from "@/lib/teams";
import { createTeam, updateTeam } from "@/lib/teams-client";

export function TeamForm({
  team,
  campuses,
  workflows,
}: {
  team?: Team;
  campuses: Campus[];
  workflows: { id: number; name: string }[];
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(event.currentTarget);
    const campus = String(formData.get("campus") || "");
    const workflow = String(formData.get("workflow") || "");

    if (!workflow) {
      setError("Choose the approval workflow this team routes through.");
      setLoading(false);
      return;
    }

    const input: TeamInput = {
      name: String(formData.get("name") || ""),
      description: String(formData.get("description") || ""),
      campus: campus ? Number(campus) : null,
      workflow: Number(workflow),
      is_active: formData.get("is_active") === "on",
    };

    try {
      if (team) {
        await updateTeam(team.id, input);
      } else {
        await createTeam(input);
      }
      router.push("/dashboard/hr-admin/teams");
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
    <form
      onSubmit={handleSubmit}
      className="grid grid-cols-1 gap-4 md:grid-cols-2"
    >
      <div>
        <label
          htmlFor="name"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Name
        </label>
        <input
          id="name"
          name="name"
          required
          defaultValue={team?.name}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          placeholder="e.g. Bunda College Faculty"
        />
      </div>

      <div>
        <label
          htmlFor="campus"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Campus
        </label>
        <select
          id="campus"
          name="campus"
          defaultValue={team?.campus ?? ""}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        >
          <option value="">No campus</option>
          {campuses.map((campus) => (
            <option key={campus.id} value={campus.id}>
              {campus.name}
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-text-muted">
          Optional. Scopes the team for reporting and history.
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
          defaultValue={team?.description}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          placeholder="Who belongs on this team"
        />
      </div>

      <div className="md:col-span-2">
        <label
          htmlFor="workflow"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Approval workflow
        </label>
        <select
          id="workflow"
          name="workflow"
          defaultValue={team?.workflow ?? ""}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        >
          <option value="">Choose a workflow…</option>
          {workflows.map((workflow) => (
            <option key={workflow.id} value={workflow.id}>
              {workflow.name}
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-text-muted">
          The approval chain this team&apos;s applications follow. It owns the
          sections, so its steps define who may act for this team.
        </p>
      </div>

      <label className="flex items-center gap-2 md:col-span-2">
        <input
          type="checkbox"
          name="is_active"
          defaultChecked={team?.is_active ?? true}
          className="size-4 rounded border-input-border text-brand-primary focus:ring-input-ring-focus"
        />
        <span className="text-sm font-medium text-text-primary">
          Active team
        </span>
      </label>

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
          {loading ? "Saving..." : team ? "Save changes" : "Create team"}
        </button>
        <Link
          href="/dashboard/hr-admin/teams"
          className="rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-text-secondary hover:bg-button-secondary-hover"
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}
