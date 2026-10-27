"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import type { EligibleApprover, Team, TeamSection } from "@/lib/teams";
import { listEligibleApprovers } from "@/lib/teams-client";
import {
  addSectionMember,
  listSectionMemberHistory,
  listSectionMembers,
  removeSectionMember,
} from "@/lib/section-members-client";
import type { SectionMember } from "@/lib/workflows";
import { Button } from "@/components/ui/button";
import { ConfirmButton } from "@/components/ui/confirm-button";

/**
 * Names the one person who decides at each step of a team's chain.
 *
 * A step has exactly one approver, so this is a picker per step rather than a
 * roster: changing the approver is a handover, and the backend closes the
 * outgoing person's period and opens the incoming one in the same action. The
 * history is kept because a person who left a step in March still signed for it.
 */
export function TeamMemberList({ team }: { team: Team }) {
  const router = useRouter();
  const [candidates, setCandidates] = useState<Record<number, EligibleApprover[]>>(
    {}
  );
  const [openMembership, setOpenMembership] = useState<
    Record<number, SectionMember | null>
  >({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<number | null>(null);
  const [history, setHistory] = useState<Record<number, SectionMember[]>>({});
  const [showHistory, setShowHistory] = useState<Record<number, boolean>>({});

  const roleIdByCode = useMemo(
    () => new Map(team.stage_roles.map((role) => [role.code, role.id])),
    [team.stage_roles]
  );

  useEffect(() => {
    let cancelled = false;
    Promise.all(
      team.sections.map(async (section) => {
        const roleId = roleIdByCode.get(section.approver_role);
        const [people, periods] = await Promise.all([
          roleId === undefined
            ? Promise.resolve([] as EligibleApprover[])
            : listEligibleApprovers(team.id, roleId, team.workflow ?? undefined),
          listSectionMembers(section.id),
        ]);
        return [section.id, { people, open: periods[0] ?? null }] as const;
      })
    )
      .then((entries) => {
        if (cancelled) return;
        const nextCandidates: Record<number, EligibleApprover[]> = {};
        const nextOpen: Record<number, SectionMember | null> = {};
        entries.forEach(([sectionId, value]) => {
          nextCandidates[sectionId] = value.people;
          nextOpen[sectionId] = value.open;
        });
        setCandidates(nextCandidates);
        setOpenMembership(nextOpen);
      })
      .catch(() => {
        if (cancelled) return;
        setError("Unable to load who may approve for this team. Please try again.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // Re-run when the server props change after an appointment, so the current
    // holder and the eligible list stay in step with the team.
  }, [team.id, team.sections, team.workflow, roleIdByCode]);

  async function appoint(section: TeamSection, userId: number) {
    setError("");
    setBusy(section.id);
    try {
      await addSectionMember(section.id, userId);
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An error occurred. Please try again."
      );
    } finally {
      setBusy(null);
    }
  }

  async function clear(section: TeamSection) {
    const membership = openMembership[section.id];
    if (!membership) return;
    setError("");
    setBusy(section.id);
    try {
      await removeSectionMember(membership.id);
      setOpenMembership((current) => ({ ...current, [section.id]: null }));
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An error occurred. Please try again."
      );
    } finally {
      setBusy(null);
    }
  }

  /**
   * History is fetched on demand and then cached, because a period is a fact
   * about the past: it does not change while this screen is open.
   */
  async function toggleHistory(sectionId: number) {
    const next = !showHistory[sectionId];
    setShowHistory((current) => ({ ...current, [sectionId]: next }));
    if (!next || history[sectionId]) {
      return;
    }
    try {
      const periods = await listSectionMemberHistory(sectionId);
      setHistory((current) => ({ ...current, [sectionId]: periods }));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An error occurred. Please try again."
      );
    }
  }

  if (team.sections.length === 0) {
    return (
      <p className="mt-3 text-sm text-text-muted">
        This team has no approval steps, so there is nobody to appoint. Add a
        step to its chain first.
      </p>
    );
  }

  return (
    <div className="mt-3">
      {loading ? (
        <p className="text-sm text-text-muted">Loading who can approve…</p>
      ) : null}

      <div className="space-y-3">
        {team.sections.map((section) => {
          const current = section.approver;
          const people = candidates[section.id] ?? [];
          // The current holder is offered even when the eligibility list has
          // moved on, so the step never reads as unstaffed while it is held.
          const options =
            current && !people.some((person) => person.id === current.id)
              ? [
                  {
                    id: current.id,
                    full_name: current.user_name,
                    email: current.user_email,
                    designation: "",
                  },
                  ...people,
                ]
              : people;
          return (
            <div
              key={section.id}
              role="group"
              aria-label={`Section ${section.order}: ${section.name}`}
              className="rounded-md border border-border-default bg-surface-card p-3"
            >
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className="grid size-6 shrink-0 place-content-center rounded-full bg-brand-primary-subtle text-xs font-semibold text-brand-primary">
                  {section.order}
                </span>
                <span className="text-sm font-medium text-text-primary">
                  {section.approver_role_label}
                </span>
                <span className="text-xs text-text-muted">{section.name}</span>
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-2">
                <label
                  className="sr-only"
                  htmlFor={`approver-${section.id}`}
                >
                  Approver for {section.name}
                </label>
                <select
                  id={`approver-${section.id}`}
                  value={current ? String(current.id) : ""}
                  disabled={busy === section.id || options.length === 0}
                  onChange={(event) => {
                    if (event.target.value) {
                      void appoint(section, Number(event.target.value));
                    }
                  }}
                  className="min-w-52 rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <option value="">Nobody appointed</option>
                  {options.map((person) => (
                    <option key={person.id} value={person.id}>
                      {person.full_name}
                      {person.designation ? ` — ${person.designation}` : ""}
                    </option>
                  ))}
                </select>
                {current ? (
                  <ConfirmButton
                    size="sm"
                    onConfirm={() => clear(section)}
                    disabled={busy === section.id}
                    loading={busy === section.id}
                    prompt={`End ${current.user_name}'s term on ${section.name}?`}
                    aria-label={`Remove ${current.user_name} from ${section.name}`}
                  >
                    Remove
                  </ConfirmButton>
                ) : null}
                <Button
                  variant="link"
                  size="sm"
                  onClick={() => void toggleHistory(section.id)}
                  aria-label={`Show past approvers of ${section.name}`}
                  aria-pressed={Boolean(showHistory[section.id])}
                  className="ml-auto"
                >
                  {showHistory[section.id]
                    ? "Hide past approvers"
                    : "Who was here before?"}
                </Button>
              </div>

              {options.length === 0 ? (
                <p className="mt-1 text-xs text-text-muted">
                  Nobody on this team holds this role yet, so this step has nobody
                  to appoint.
                </p>
              ) : null}

              {showHistory[section.id] ? (
                <PastApprovers
                  section={section}
                  periods={history[section.id] ?? []}
                />
              ) : null}
            </div>
          );
        })}
      </div>

      {error && <p className="mt-3 text-sm text-status-rejected">{error}</p>}

      <p className="mt-2 text-xs text-text-muted">Each step has exactly one approver.</p>
    </div>
  );
}

/**
 * The periods a step has had, closed ones included.
 *
 * Worth showing: a person who left a step in March still signed for it, and
 * "who could act on the second" has to be answerable long after the handover.
 */
function PastApprovers({
  section,
  periods,
}: {
  section: TeamSection;
  periods: SectionMember[];
}) {
  const past = periods.filter((period) => !period.is_effective);
  if (past.length === 0) {
    return (
      <p className="mt-2 text-xs text-text-muted">
        Nobody has held {section.name} in the past.
      </p>
    );
  }
  return (
    <ul className="mt-2 space-y-1 border-l-2 border-border-default pl-3">
      {past.map((period) => (
        <li key={period.id} className="text-xs text-text-muted">
          <span className="font-medium text-text-secondary">
            {period.user_name}
          </span>{" "}
          {formatDate(period.effective_from)} to{" "}
          {period.effective_to ? formatDate(period.effective_to) : "open"}
        </li>
      ))}
    </ul>
  );
}

function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}