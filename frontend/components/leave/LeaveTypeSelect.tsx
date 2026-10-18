"use client";

import { useEffect, useState } from "react";

import { getLeaveTypes, type LeaveType } from "@/lib/services/leaveTypes";
import { Field } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface LeaveTypeSelectProps {
  value: number | null;
  onChange: (id: number | null) => void;
  disabled?: boolean;
  /**
   * When provided, the parent owns the list (and its loading/error state) so a
   * flow that also needs the selected type's flags — the wizard's
   * "does this type need documents?" decision — fetches once. Omitted, the
   * select fetches the list itself.
   */
  types?: LeaveType[];
  loading?: boolean;
  error?: string | null;
}

export function LeaveTypeSelect({
  value,
  onChange,
  disabled,
  types,
  loading,
  error,
}: LeaveTypeSelectProps) {
  const controlled = types !== undefined;
  const [internalTypes, setInternalTypes] = useState<LeaveType[]>([]);
  const [internalError, setInternalError] = useState("");
  const [internalLoading, setInternalLoading] = useState(false);

  useEffect(() => {
    if (controlled) return;
    let cancelled = false;
    const load = async () => {
      setInternalLoading(true);
      try {
        const data = await getLeaveTypes();
        if (!cancelled) {
          setInternalTypes(data);
          setInternalError("");
        }
      } catch {
        if (!cancelled) {
          setInternalError("Unable to load leave types.");
        }
      } finally {
        if (!cancelled) {
          setInternalLoading(false);
        }
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [controlled]);

  const options = controlled ? types : internalTypes;
  const isLoading = controlled ? Boolean(loading) : internalLoading;
  const loadError = controlled ? (error ?? "") : internalError;
  // Resolving the label here keeps the trigger correct when a value is set
  // programmatically (draft reload, smart defaults) without the listbox having
  // been opened — Radix only portals an item's text in once it has mounted.
  const selectedName = options.find((t) => t.id === value)?.name;

  return (
    <Field
      label="Leave Type"
      htmlFor="leave-type"
      error={loadError || null}
      hint={
        !isLoading && !loadError && options.length === 0
          ? "No leave types are available for your grade yet. Ask HR to grant an entitlement for your grade before applying."
          : undefined
      }
    >
      <Select
        value={value === null || value === undefined ? "" : String(value)}
        onValueChange={(next) => onChange(next ? Number(next) : null)}
        disabled={disabled || isLoading}
      >
        <SelectTrigger id="leave-type" aria-label="Leave Type">
          <SelectValue placeholder={isLoading ? "Loading..." : "Select leave type"}>
            {selectedName}
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="">{isLoading ? "Loading..." : "Select leave type"}</SelectItem>
          {options.map((t) => (
            <SelectItem key={t.id} value={String(t.id)}>
              {t.name}
              {t.entitlementDays ? ` — ${t.entitlementDays} days` : ""}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </Field>
  );
}
