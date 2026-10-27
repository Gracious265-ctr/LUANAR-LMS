"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { UserCog } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmButton } from "@/components/ui/confirm-button";
import { Alert } from "@/components/ui/states";
import type { Employee } from "@/lib/employees";
import { clearTeamManager, setTeamManager } from "@/lib/teams-client";

/**
 * Who runs this team.
 *
 * The manager is the one person who staffs the roster, builds the team's
 * chains, and chooses its default. They need not hold a team-scoped role: an
 * institution-wide approver is designated on the team itself, which is the case
 * this panel exists to make possible. Only HR may change the designation — a
 * manager runs the team, they do not name their successor.
 *
 * The picker offers every active employee with a record, in either half of the
 * institution, because the person who runs a team is not required to share its
 * category. It marks the team's current manager with `aria-current` so the
 * select still answers "who runs this?" before the page is saved.
 */
export function TeamManagerPanel({
  team,
  employees,
  canManage = false,
}: {
  team: { id: number; name: string; manager_user: number | null; manager_name: string };
  employees: Employee[];
  /** Whether the viewer may change the designation. HR-only. */
  canManage?: boolean;
}) {
  const router = useRouter();
  const [selected, setSelected] = useState(
    team.manager_user == null ? "" : String(team.manager_user)
  );
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  // Only somebody with an employee record can run a team: the backend refuses a
  // user with nothing to manage, so the picker does not offer them.
  const options = useMemo(
    () =>
      [...employees]
        .filter((employee) => employee.is_active)
        .sort((left, right) => left.full_name.localeCompare(right.full_name)),
    [employees]
  );

  async function apply(userId: number) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const updated = await setTeamManager(team.id, userId);
      setSelected(
        updated.manager_user == null ? "" : String(updated.manager_user)
      );
      setNotice(`${updated.manager_name} now runs ${team.name}.`);
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "The team manager could not be changed."
      );
    } finally {
      setBusy(false);
    }
  }

  async function clear() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await clearTeamManager(team.id);
      setSelected("");
      setNotice(`${team.name} no longer has a manager.`);
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "The team manager could not be removed."
      );
    } finally {
      setBusy(false);
    }
  }

  const current = team.manager_user;

  return (
    <div className="space-y-3">
      {error && <Alert tone="error">{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}

      <div className="flex flex-wrap items-center gap-2 text-sm">
        {current == null ? (
          <p className="text-text-secondary">
            Nobody runs this team yet. HR names the manager before its roster or
            chains can be changed.
          </p>
        ) : (
          <p className="flex flex-wrap items-center gap-2 text-text-primary">
            <UserCog className="h-4 w-4 text-text-muted" aria-hidden="true" />
            <span className="font-medium">{team.manager_name}</span>
            <Badge size="sm" tone="info">
              Manager
            </Badge>
          </p>
        )}
      </div>

      {canManage ? (
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (!selected) {
              setError("Choose somebody to run this team.");
              return;
            }
            void apply(Number(selected));
          }}
        >
          <div className="min-w-56 flex-1">
            <label
              className="mb-1 block text-xs font-medium text-text-secondary"
              htmlFor="team-manager"
            >
              Designate a manager
            </label>
            <select
              id="team-manager"
              value={selected}
              onChange={(event) => {
                setSelected(event.target.value);
                setError("");
              }}
              disabled={busy}
              className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
            >
              <option value="">Choose a person</option>
              {options.map((employee) => (
                <option
                  key={employee.user_id}
                  value={employee.user_id}
                  aria-current={
                    employee.user_id === current ? "true" : undefined
                  }
                >
                  {employee.full_name}
                  {employee.designation ? ` — ${employee.designation}` : ""}
                  {employee.user_id === current ? " (current manager)" : ""}
                </option>
              ))}
            </select>
          </div>
          <Button
            type="submit"
            disabled={busy || !selected || Number(selected) === current}
            loading={busy}
          >
            Make manager
          </Button>
          {current != null && (
            <ConfirmButton
              variant="secondary"
              onConfirm={clear}
              disabled={busy}
              prompt={`Remove ${team.manager_name} as manager of ${team.name}? The team keeps its members and chains.`}
            >
              Remove manager
            </ConfirmButton>
          )}
        </form>
      ) : (
        <p className="text-xs text-text-muted">
          Only HR can change who manages a team.
        </p>
      )}

      {canManage && options.length === 0 && (
        <p className="text-xs text-text-muted">
          No active employees with a record were found to name.
        </p>
      )}
    </div>
  );
}
