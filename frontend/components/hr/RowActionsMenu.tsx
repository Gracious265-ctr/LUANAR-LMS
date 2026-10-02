"use client";

import type { ReactNode } from "react";
import { MoreHorizontal } from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export interface RowAction {
  id: string;
  label: string;
  icon?: ReactNode;
  /** Renders the label in the rejected colour, for destructive actions. */
  destructive?: boolean;
  disabled?: boolean;
  onSelect: () => void;
}

export interface RowActionsMenuProps {
  /**
   * Names the record the menu acts on. Without it a table of these is a column
   * of identically labelled controls that a screen reader reads out as
   * "Actions, Actions, Actions" with no way to tell the rows apart.
   */
  label: string;
  actions: RowAction[];
  /** Optional heading, for menus whose meaning is not obvious from the row. */
  heading?: string;
}

/**
 * A row's secondary actions behind a single `⋯` trigger.
 *
 * This is the one place a non-modal popover is the right surface. A menu is a
 * launcher: it opens, you pick something, it closes, and there is no partially
 * filled-in work to lose by pressing Escape — which is exactly what rules a
 * popover out for the create/edit forms.
 *
 * Not wired to any table yet. It exists so rows that currently carry three or
 * four inline icon buttons can collapse to one trigger without each table
 * re-deciding how to render a menu.
 */
export function RowActionsMenu({ label, actions, heading }: RowActionsMenuProps) {
  if (actions.length === 0) return null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        type="button"
        aria-label={label}
        title={label}
        className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-border-default bg-button-secondary text-text-secondary transition-colors hover:bg-button-secondary-hover hover:text-text-primary"
      >
        <MoreHorizontal className="h-4 w-4" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {heading && <DropdownMenuLabel>{heading}</DropdownMenuLabel>}
        {actions.map((action, index) => (
          <div key={action.id}>
            {/* A separator above each destructive action, so "Deactivate" is not
                one unremarkable entry among "Edit" and "View audit". */}
            {(action.destructive || actions[index - 1]?.destructive) && (
              <DropdownMenuSeparator />
            )}
            <DropdownMenuItem
              disabled={action.disabled}
              onSelect={action.onSelect}
              className={action.destructive ? "text-status-rejected" : undefined}
            >
              {action.icon}
              {action.label}
            </DropdownMenuItem>
          </div>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
