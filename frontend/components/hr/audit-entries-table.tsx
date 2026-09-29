import type { AuditEntry } from "@/lib/audit";
import { TARGET_TYPE_LABELS } from "@/lib/audit";
import { AuditActionPill, auditChangesText, auditEditHref } from "./audit-meta";
import { EditActionLink } from "./edit-action-link";

export function AuditEntriesTable({ entries }: { entries: AuditEntry[] }) {
  if (entries.length === 0) {
    return (
      <div className="py-12 text-center text-text-muted">
        <p className="text-base font-medium text-text-primary">No audit entries</p>
        <p className="mt-1 text-sm">
          Actions you take here — configuration changes, decisions, and
          submissions — are recorded in the administrative history.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[70rem] text-sm">
        <thead>
          <tr className="border-b border-border-default text-left text-xs font-medium uppercase tracking-wide text-text-muted">
            <th className="py-3 pr-4">Actor</th>
            <th className="py-3 pr-4">Action</th>
            <th className="py-3 pr-4">Target</th>
            <th className="py-3 pr-4">Details</th>
            <th className="py-3">When</th>
            <th className="py-3 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => {
            const editHref = auditEditHref(entry);
            return (
              <tr
                key={entry.id}
                className="border-b border-border-default transition-colors hover:bg-surface-hover"
              >
                <td className="py-3 pr-4 text-text-primary">
                  <div className="font-medium">
                    {entry.actor_name || (entry.actor ? `#${entry.actor}` : "System")}
                  </div>
                </td>
                <td className="py-3 pr-4">
                  <AuditActionPill action={entry.action} />
                </td>
                <td className="max-w-85 break-words py-3 pr-4 text-text-secondary">
                  <div className="text-xs text-text-muted">
                    {TARGET_TYPE_LABELS[entry.target_type] || entry.target_type}
                  </div>
                  <div className="break-all font-medium text-text-primary">
                    {entry.target_summary}
                  </div>
                </td>
                <td className="max-w-md break-words py-3 pr-4 text-text-secondary">
                  {auditChangesText(entry)}
                </td>
                <td className="py-3 text-text-secondary">
                  <div className="whitespace-nowrap">
                    {new Date(entry.created_at).toLocaleDateString()}
                  </div>
                  <div className="text-xs text-text-muted">
                    {new Date(entry.created_at).toLocaleTimeString()}
                  </div>
                </td>
                <td className="py-3 text-right">
                  {editHref ? (
                    <EditActionLink href={editHref} />
                  ) : (
                    <span className="text-xs text-text-muted">{"\u2014"}</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}