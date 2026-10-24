"use client";

import { useState } from "react";
import { Bell } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useUnreadCount } from "@/lib/hooks/useUnreadCount";

import { NotificationPopoverContent } from "./NotificationPopover";

/**
 * The always-reachable bell in the shared top bar (unit 08 §2.3–2.4).
 *
 * Lives in the dashboard shell's header, so it is present on every page of
 * every module. The trigger matches the header's other icon controls
 * (`secondary`, `size-10` — see ThemeToggle), and the badge follows the
 * project's absence-over-zero rule: nothing at 0, the number at 1–9, "9+"
 * beyond that.
 */
export function NotificationBell() {
  const { data: unreadCount, refetch } = useUnreadCount();
  const [open, setOpen] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="secondary"
          aria-label="Notifications"
          title="Notifications"
          className="relative size-10 shrink-0 p-0"
        >
          <Bell className="h-4 w-4" aria-hidden="true" />
          {unreadCount > 0 && (
            <span
              aria-hidden="true"
              className="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-medium text-destructive-foreground"
            >
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      {/* `align="end"` keeps the panel right-aligned under the bell instead of
          centred across the screen — a popover, not the Dialog. */}
      <PopoverContent align="end" className="w-80 rounded-xl p-0 shadow-lg">
        <NotificationPopoverContent
          onNavigate={() => setOpen(false)}
          onCountChanged={() => void refetch()}
        />
      </PopoverContent>
    </Popover>
  );
}
