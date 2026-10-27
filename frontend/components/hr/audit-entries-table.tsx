import type { AuditEntry } from "@/lib/audit";
import { TARGET_TYPE_LABELS } from "@/lib/audit";
import { AuditActionPill, auditChangesText, auditEditHref } from "./audit-meta";
import { EditActionLink } from "./edit-action-link";
import { Avatar } from "@/components/ui/Avatar";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export function AuditEntriesTable({ entries }: { entries: AuditEntry[] }) {
  if (entries.length === 0) {
    return (
      <div className="py-12 text-center text-text-muted">
        <p className="text-base font-medium text-text-primary">No audit entries</p>
        <p className="mt-1 text-sm">Actions taken here are recorded in the administrative history.</p>
      </div>
    );
  }

  return (
    <Table className="min-w-[70rem]">
      <TableHeader>
        <TableRow>
          <TableHead>Actor</TableHead>
          <TableHead>Action</TableHead>
          <TableHead>Target</TableHead>
          <TableHead>Details</TableHead>
          <TableHead>When</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {entries.map((entry) => {
          const editHref = auditEditHref(entry);
          return (
            <TableRow
              key={entry.id}
            >
              <TableCell className="text-text-primary">
                <div className="flex items-center gap-2">
                  {entry.actor_name ? (
                    <Avatar
                      name={entry.actor_name}
                      userId={entry.actor ?? entry.actor_name}
                      size="sm"
                    />
                  ) : null}
                  <div className="font-medium">
                    {entry.actor_name || (entry.actor ? `#${entry.actor}` : "System")}
                  </div>
                </div>
              </TableCell>
              <TableCell>
                <AuditActionPill action={entry.action} />
              </TableCell>
              <TableCell className="max-w-85 break-words text-text-secondary">
                <div className="text-xs text-text-muted">
                  {TARGET_TYPE_LABELS[entry.target_type] || entry.target_type}
                </div>
                <div className="break-all font-medium text-text-primary">
                  {entry.target_summary}
                </div>
              </TableCell>
              <TableCell className="max-w-md break-words text-text-secondary">
                {auditChangesText(entry)}
              </TableCell>
              <TableCell className="text-text-secondary">
                <div className="whitespace-nowrap">
                  {new Date(entry.created_at).toLocaleDateString()}
                </div>
                <div className="text-xs text-text-muted">
                  {new Date(entry.created_at).toLocaleTimeString()}
                </div>
              </TableCell>
              <TableCell className="text-right">
                {editHref ? (
                  <EditActionLink href={editHref} />
                ) : (
                  <span className="text-xs text-text-muted">{"\u2014"}</span>
                )}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}