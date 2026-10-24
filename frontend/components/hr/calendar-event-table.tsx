import Link from "next/link";

import type { CalendarEvent } from "@/lib/financial-years";
import { deleteCalendarEvent } from "@/lib/financial-years-client";
import { DeleteRowButton } from "./delete-row-button";
import { EditActionLink, EditIconButton } from "./edit-action-link";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/states";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export function CalendarEventTable({
  events,
  onEdit,
}: {
  events: CalendarEvent[];
  /**
   * Opens the edit overlay for this row. Omitted on hosts that still link
   * to the standalone edit page, in which case the pencil renders as a link.
   */
  onEdit?: (id: number) => void;
}) {
  if (events.length === 0) {
    return (
      <EmptyState
        title="No events"
        description="Add institutional dates such as graduations, exams, or closures."
      />
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Title</TableHead>
          <TableHead>Period</TableHead>
          <TableHead>Affects leave</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {events.map((event) => (
          <TableRow key={event.id}>
            <TableCell>
              <Link
                href={`/dashboard/hr-admin/calendar/events/${event.id}/edit`}
                className="font-medium text-brand-primary hover:text-brand-primary-hover"
              >
                {event.title}
              </Link>
            </TableCell>
            <TableCell className="text-text-secondary">
              {event.start_date === event.end_date
                ? event.start_date
                : `${event.start_date} – ${event.end_date}`}
            </TableCell>
            <TableCell>
              <Badge
                size="sm"
                tone={event.affects_leave_calculation ? "rejected" : "muted"}
              >
                {event.affects_leave_calculation ? "Yes" : "No"}
              </Badge>
            </TableCell>
            <TableCell>
              <div className="flex items-center justify-end gap-2">
                {onEdit ? (
                  <EditIconButton
                    onClick={() => onEdit(event.id)}
                    label={`Edit ${event.title}`}
                  />
                ) : (
                  <EditActionLink
                    href={`/dashboard/hr-admin/calendar/events/${event.id}/edit`}
                  />
                )}
                <DeleteRowButton
                  label={`Delete ${event.title}`}
                  prompt={`Delete ${event.title}?`}
                  onDelete={() => deleteCalendarEvent(event.id)}
                />
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
