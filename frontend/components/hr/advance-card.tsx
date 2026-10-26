import { Workflow } from "@/lib/workflows";

interface AdvanceCardProps {
  workflow: Workflow;
}

export async function AdvanceCard({ workflow }: AdvanceCardProps) {
  const team = workflow.team_name;
  const state = workflow.state;
  const effective = workflow.effective_from ?? "—";

  const steps = workflow.sections.length;
  const staffed = workflow.sections.filter((s) => s.resolution.user_name).length;
  const members = workflow.members.length;

  const routing = workflow.is_routing
    ? "This chain is the team's default — the fallback for unenrolled staff."
    : "This chain is not the team's default; it only routes the people enrolled on it.";

  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm"
      aria-label="Chain details"
    >
      <div className="space-y-1">
        <dt className="text-xs text-text-muted">Team</dt>
        <dd className="font-medium text-text-primary">{team}</dd>
      </div>
      <div className="space-y-1">
        <dt className="text-xs text-text-muted">State</dt>
        <dd className="font-medium text-text-primary">{state}</dd>
      </div>
      <div className="space-y-1">
        <dt className="text-xs text-text-muted">Effective from</dt>
        <dd className="font-medium text-text-primary">{effective}</dd>
      </div>
      <div className="space-y-1">
        <dt className="text-xs text-text-muted">Steps</dt>
        <dd className="font-medium text-text-primary">{staffed} of {steps} staffed</dd>
      </div>
      <div className="space-y-1">
        <dt className="text-xs text-text-muted">Members</dt>
        <dd className="font-medium text-text-primary">{members} on this chain</dd>
      </div>
      <div className="space-y-1 col-span-2">
        <dt className="text-xs text-text-muted">Routing</dt>
        <dd className="text-text-primary">{routing}</dd>
      </div>
    </dl>
  );
}
