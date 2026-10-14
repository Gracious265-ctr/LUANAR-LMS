"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { CircleCheck, CirclePlay, CircleStop } from "lucide-react";

import type { Team, TeamReadiness } from "@/lib/teams";
import { activateTeam, deactivateTeam, validateTeam } from "@/lib/teams-client";
import { STATUS_STYLES } from "@/lib/status-styles";

/**
 * Putting a team into force, and taking it out.
 *
 * These are buttons rather than a checkbox because each is a decision with a
 * consequence: activation refuses a chain that cannot route, and retirement
 * stops new applications without touching the ones already inside the team.
 * A form field could do neither.
 *
 * Readiness is asked for rather than guessed, and the answer is a list, so a
 * team with three problems takes one pass instead of three refused clicks.
 */
export function TeamLifecycleActions({ team }: { team: Team }) {
  const router = useRouter();
  const [readiness, setReadiness] = useState<TeamReadiness | null>(null);
  const [busy, setBusy] = useState<"" | "validate" | "activate" | "deactivate">(
    ""
  );
  const [error, setError] = useState("");

  async function run(kind: "validate" | "activate" | "deactivate") {
    setError("");
    setBusy(kind);
    try {
      if (kind === "validate") {
        setReadiness(await validateTeam(team.id));
      } else {
        if (kind === "activate") {
          await activateTeam(team.id);
        } else {
          await deactivateTeam(team.id);
        }
        setReadiness(null);
        router.refresh();
      }
    } catch (err) {
      // A refused activation comes back carrying the reasons, so they are shown
      // rather than collapsed into "something went wrong".
      const issues = (err as { readiness?: TeamReadiness }).readiness;
      if (issues) {
        setReadiness(issues);
      } else {
        setError(
          err instanceof Error ? err.message : "An error occurred. Please try again."
        );
      }
    } finally {
      setBusy("");
    }
  }

  const isDraft = team.status === "draft";
  const isActive = team.status === "active";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => run("validate")}
          disabled={busy !== ""}
          className="inline-flex items-center gap-1.5 rounded-md border border-border-default bg-button-secondary px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy === "validate" ? "Checking…" : "Check readiness"}
        </button>

        {isActive ? (
          <button
            type="button"
            onClick={() => run("deactivate")}
            disabled={busy !== ""}
            className="inline-flex items-center gap-1.5 rounded-md border border-border-default bg-button-secondary px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            <CircleStop className="h-4 w-4" />
            {busy === "deactivate" ? "Retiring…" : "Retire team"}
          </button>
        ) : (
          <button
            type="button"
            onClick={() => run("activate")}
            disabled={busy !== ""}
            className="inline-flex items-center gap-1.5 rounded-md bg-button-primary px-3 py-1.5 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            <CirclePlay className="h-4 w-4" />
            {busy === "activate"
              ? "Activating…"
              : isDraft
                ? "Put into force"
                : "Bring back into force"}
          </button>
        )}
      </div>

      {readiness && <ReadinessReport readiness={readiness} />}

      {error && (
        <p role="alert" className="text-sm text-status-rejected">
          {error}
        </p>
      )}
    </div>
  );
}

function ReadinessReport({ readiness }: { readiness: TeamReadiness }) {
  if (readiness.ready) {
    return (
      <div
        role="status"
        className={`rounded-md p-3 text-sm ${STATUS_STYLES.approved}`}
      >
        <span className="inline-flex items-center gap-1.5 font-medium">
          <CircleCheck className="h-4 w-4" />
          {readiness.team} is ready to put into force.
        </span>
      </div>
    );
  }

  return (
    <div
      role="status"
      className={`rounded-md p-3 text-sm ${STATUS_STYLES.pending}`}
    >
      <p className="font-medium">
        {readiness.team} cannot be put into force yet. Fix {readiness.issues.length}{" "}
        {readiness.issues.length === 1 ? "problem" : "problems"}:
      </p>
      <ul className="mt-1.5 list-inside list-disc space-y-1">
        {readiness.issues.map((issue, index) => (
          <li key={`${issue.code}-${issue.field}-${index}`}>{issue.message}</li>
        ))}
      </ul>
    </div>
  );
}
