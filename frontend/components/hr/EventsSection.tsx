"use client";

import { useRouter } from "next/navigation";

import { Plus } from "lucide-react";

import type { CalendarEvent } from "@/lib/financial-years";
import { useOverlayParam } from "@/lib/hooks/useOverlayParam";
import { AdminFormOverlay } from "@/components/hr/AdminFormOverlay";
import { CalendarEventForm } from "@/components/hr/calendar-event-form";
import { CalendarEventTable } from "@/components/hr/calendar-event-table";
import { Button } from "@/components/ui/button";

/** Query key for the event overlay. Distinct from `holiday` and `financialYear`. */
export const EVENT_PARAM = "event";

/**
 * The events half of the "Holidays & Events" tab, as a create/edit overlay.
 *
 * Events are informational by default; `affects_leave_calculation` is the one
 * field that promotes an event to a period leave must account for, so it is a
 * labelled checkbox rather than a hidden default (§3.6).
 */
export function EventsSection({ events }: { events: CalendarEvent[] }) {
  const router = useRouter();
  const overlay = useOverlayParam(EVENT_PARAM);

  const editing =
    overlay.target !== null && !overlay.isCreate
      ? events.find((row) => String(row.id) === overlay.target)
      : undefined;

  return (
    <>
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-text-primary">Events</h3>
          <p className="mt-1 text-sm text-text-secondary">
            Institutional dates such as graduations, exams, or closures.
          </p>
        </div>
        <Button variant="primary" onClick={overlay.openCreate} className="shrink-0">
          <Plus className="h-4 w-4" />
          New event
        </Button>
      </div>

      <CalendarEventTable events={events} onEdit={overlay.openEdit} />

      <AdminFormOverlay
        open={overlay.isOpen}
        title={
          editing
            ? `Edit ${editing.title}`
            : overlay.isCreate
              ? "New event"
              : "Edit event"
        }
        description={
          editing
            ? "Update the event and whether it affects leave calculations."
            : "Add an institutional date. It stays informational unless you say it affects leave."
        }
        onOpenChange={(open) => {
          if (!open) overlay.close();
        }}
        notFound={
          editing === undefined && !overlay.isCreate
            ? "That event is no longer in the list. It may have been deleted."
            : undefined
        }
      >
        <CalendarEventForm
          event={editing}
          onSuccess={() => {
            overlay.close();
            router.refresh();
          }}
          onCancel={overlay.close}
        />
      </AdminFormOverlay>
    </>
  );
}
