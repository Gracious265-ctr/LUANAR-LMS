"use client";

import { Field } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { PlanScope } from "@/lib/plans/types";

/**
 * The calendar's scope dropdown (spec 3.6).
 *
 * A regular employee's scope list is a single entry — their own unit — so there
 * is nothing to choose and nothing renders. A unit head's list widens, so the
 * same page gains this one control without a per-role sidebar.
 */
export function ScopeSelector({
  scopes,
  value,
  onChange,
}: {
  scopes: PlanScope[];
  value: string | null;
  onChange: (scope: string) => void;
}) {
  if (scopes.length <= 1) return null;

  return (
    <Field label="Scope" htmlFor="plan-scope">
      <Select
        value={value ?? scopes[0].id}
        onValueChange={(next) => onChange(next)}
      >
        <SelectTrigger id="plan-scope" aria-label="Calendar scope">
          <SelectValue placeholder="Select a scope" />
        </SelectTrigger>
        <SelectContent>
          {scopes.map((scope) => (
            <SelectItem key={scope.id} value={scope.id}>
              {scope.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </Field>
  );
}
