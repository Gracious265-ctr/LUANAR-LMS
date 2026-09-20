import type { Reassignment } from "@/lib/reassignments";

export function ReassignmentTable({
  reassignments,
}: {
  reassignments: Reassignment[];
}) {
  if (reassignments.length === 0) {
    return (
      <div className="py-12 text-center text-text-muted">
        <p className="text-base font-medium text-text-primary">
          No reassignments yet
        </p>
        <p className="mt-1 text-sm">
          Reassign a pending application from the intervention queue above to
          record the first reassignment.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border-default text-left text-xs font-medium uppercase tracking-wide text-text-muted">
            <th className="py-3 pr-4">Application</th>
            <th className="py-3 pr-4">Employee</th>
            <th className="py-3 pr-4">From → To</th>
            <th className="py-3 pr-4">Reason</th>
            <th className="py-3">Decided</th>
          </tr>
        </thead>
        <tbody>
          {reassignments.map((reassignment) => (
            <tr
              key={reassignment.id}
              className="border-b border-border-default transition-colors hover:bg-surface-hover"
            >
              <td className="py-3 pr-4 font-medium text-text-primary">
                {reassignment.reference_number || "\u2014"}
              </td>
              <td className="py-3 pr-4 text-text-secondary">
                {reassignment.employee_name}
              </td>
              <td className="py-3 pr-4 text-text-secondary">
                <span className="text-text-muted">
                  {reassignment.from_approver_name || "Unassigned"}
                </span>
                <span className="mx-1 text-text-muted">→</span>
                <span className="font-medium text-text-primary">
                  {reassignment.to_approver_name}
                </span>
              </td>
              <td className="py-3 pr-4 text-text-secondary">
                {reassignment.reason}
              </td>
              <td className="py-3 text-text-secondary">
                <div>{reassignment.decided_by_name}</div>
                <div className="text-xs text-text-muted">
                  {new Date(reassignment.created_at).toLocaleString()}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}