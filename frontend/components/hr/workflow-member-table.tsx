import type { WorkflowMember } from "@/lib/team-members";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

/**
 * The people enrolled on one chain, as a roster table.
 *
 * A table rather than a list because the screen answers three questions at
 * once — who is on the chain, what their role here is, and how to reach them —
 * and a column per answer is what makes the third member comparable with the
 * first. The workflow detail payload supplies exactly these fields (see
 * `WorkflowSerializer.get_members`, which delegates to the member serializer).
 */
export function WorkflowMemberTable({
  members,
  empty,
}: {
  members: WorkflowMember[];
  /** Replaces the default empty state when the host has a better sentence. */
  empty?: React.ReactNode;
}) {
  if (members.length === 0) {
    return (
      empty ?? (
        <p className="mt-3 rounded-md border border-dashed border-border-default p-3 text-sm text-text-muted">
          No members yet. A team manager can add them from Edit steps.
        </p>
      )
    );
  }

  return (
    <div className="mt-3 overflow-hidden rounded-md border border-border-default">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Designation</TableHead>
            <TableHead>Email</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {members.map((member) => (
            <TableRow key={member.id}>
              <TableCell className="font-medium text-text-primary">
                <span className="flex flex-wrap items-center gap-1.5">
                  {member.user_name}
                  {member.is_wide_approver && (
                    <Badge size="sm" tone="muted">
                      Wide approver
                    </Badge>
                  )}
                </span>
              </TableCell>
              <TableCell>
                {member.designation || (
                  <span className="text-text-muted">—</span>
                )}
              </TableCell>
              <TableCell>
                {member.user_email ? (
                  <a
                    href={`mailto:${member.user_email}`}
                    className="text-brand-primary hover:text-brand-primary-hover"
                  >
                    {member.user_email}
                  </a>
                ) : (
                  <span className="text-text-muted">—</span>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
