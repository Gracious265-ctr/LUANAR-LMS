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
}

export function LeaveTypeSelect({
  value,
  onChange,
  disabled,
}: LeaveTypeSelectProps) {
  const [types, setTypes] = useState<LeaveType[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      try {
        const data = await getLeaveTypes();
        if (!cancelled) {
          setTypes(data);
          setError("");
        }
      } catch {
        if (!cancelled) {
          setError("Unable to load leave types.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Field
      label="Leave Type"
      htmlFor="leave-type"
      error={error || null}
      hint={
        !loading && !error && types.length === 0
          ? "No leave types are available for your grade yet. Ask HR to grant an entitlement for your grade before applying."
          : undefined
      }
    >
      <Select
        value={value === null || value === undefined ? "" : String(value)}
        onValueChange={(next) => onChange(next ? Number(next) : null)}
        disabled={disabled || loading}
      >
        <SelectTrigger id="leave-type" aria-label="Leave Type">
          <SelectValue placeholder={loading ? "Loading..." : "Select leave type"} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="">{loading ? "Loading..." : "Select leave type"}</SelectItem>
          {types.map((t) => (
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
