"use client";

import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ListSearch } from "@/components/ui/list-search";
import { EmptyState } from "@/components/ui/states";

/** The fields the picker needs, whichever pool the caller reads. */
export interface PickerEmployee {
  /** The value the caller writes; a user id for every pool here. */
  id: number;
  full_name: string;
  email?: string;
  designation?: string;
}

/**
 * Pick several employees in one pass.
 *
 * Both rosters — a team's members and a chain's normal members — used to add a
 * person per click from a single select. Selecting several people is one
 * decision there, so the picker holds the selection until the caller confirms
 * it, and the caller writes the whole list once. The search box narrows the
 * local pool, because both pools are already loaded on the page.
 *
 * Selection is deliberately not preserved across opens: reopening a picker
 * after a save should start a new decision rather than resurrect people the
 * previous write has already placed.
 */
export function EmployeePickerDialog({
  open,
  onOpenChange,
  title,
  description,
  employees,
  onConfirm,
  confirmLabel,
  busy = false,
  error = "",
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  employees: PickerEmployee[];
  onConfirm: (ids: number[]) => void;
  confirmLabel: (count: number) => string;
  busy?: boolean;
  error?: string;
}) {
  const [selected, setSelected] = useState<number[]>([]);
  const [search, setSearch] = useState("");

  // Adjust the selection when the caller opens the picker rather than running
  // an effect: a fresh decision starts empty, while closing and reopening in
  // the same render pass is still one transition.
  const [wasOpen, setWasOpen] = useState(open);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) {
      setSelected([]);
      setSearch("");
    }
  }

  const visible = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return employees;
    return employees.filter((person) =>
      [person.full_name, person.email, person.designation].some((value) =>
        (value ?? "").toLowerCase().includes(query)
      )
    );
  }, [employees, search]);

  const visibleIds = visible.map((person) => person.id);
  const allVisible =
    visibleIds.length > 0 && visibleIds.every((id) => selected.includes(id));
  const someVisible = visibleIds.some((id) => selected.includes(id));

  function toggle(id: number) {
    setSelected((current) =>
      current.includes(id)
        ? current.filter((candidate) => candidate !== id)
        : [...current, id]
    );
  }

  function toggleAllVisible() {
    setSelected((current) => {
      if (allVisible) {
        return current.filter((id) => !visibleIds.includes(id));
      }
      return [...new Set([...current, ...visibleIds])];
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        {employees.length === 0 ? (
          <EmptyState
            title="Nobody can be added"
            description="There is no eligible employee in this list."
          />
        ) : (
          <>
            <ListSearch
              value={search}
              onChange={setSearch}
              label="Search employees to add"
              placeholder="Search by name, email, or designation..."
            />

            {visible.length === 0 ? (
              <p className="rounded-md border border-dashed border-border-default p-4 text-sm text-text-muted">
                No employees match this search.
              </p>
            ) : (
              <>
                <label
                  htmlFor="picker-select-all"
                  className="flex cursor-pointer items-center gap-2 text-sm font-medium text-text-primary"
                >
                  <Checkbox
                    id="picker-select-all"
                    aria-label="Select all shown"
                    checked={allVisible ? true : someVisible ? "indeterminate" : false}
                    onCheckedChange={toggleAllVisible}
                  />
                  Select all shown
                  <span className="font-normal text-text-muted">
                    ({visible.length})
                  </span>
                </label>

                <ul className="max-h-72 divide-y divide-border-default overflow-y-auto rounded-md border border-border-default">
                  {visible.map((person) => (
                    <li key={person.id}>
                      <label
                        htmlFor={`picker-employee-${person.id}`}
                        className="flex cursor-pointer items-start gap-3 px-3 py-2"
                      >
                        <Checkbox
                          id={`picker-employee-${person.id}`}
                          aria-label={person.full_name}
                          checked={selected.includes(person.id)}
                          onCheckedChange={() => toggle(person.id)}
                          className="mt-0.5"
                        />
                        <span className="min-w-0">
                          <span className="block text-sm font-medium text-text-primary">
                            {person.full_name}
                          </span>
                          <span className="block text-xs text-text-muted">
                            {[person.designation, person.email]
                              .filter(Boolean)
                              .join(" · ")}
                          </span>
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </>
        )}

        {error && <p className="text-sm text-status-rejected">{error}</p>}

        <DialogFooter>
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            disabled={selected.length === 0 || busy}
            loading={busy}
            onClick={() => onConfirm(selected)}
          >
            {confirmLabel(selected.length)}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
