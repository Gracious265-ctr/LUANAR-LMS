"use client";

import { useEffect, useState } from "react";

import { getLeaveTypes, type LeaveType } from "@/lib/services/leaveTypes";

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
    <div>
      <label
        htmlFor="leave-type"
        className="block text-sm font-medium text-text-secondary mb-1.5"
      >
        Leave Type
      </label>
      <select
        id="leave-type"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
        disabled={disabled || loading}
        className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-1 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:bg-input-disabled"
      >
        <option value="">{loading ? "Loading..." : "Select leave type"}</option>
        {types.map((t) => (
          <option key={t.id} value={t.id}>
            {t.name}
            {t.entitlementDays ? ` — ${t.entitlementDays} days` : ""}
          </option>
        ))}
      </select>
      {error && (
        <p className="mt-1 text-xs text-status-rejected">{error}</p>
      )}
      {!loading && !error && types.length === 0 && (
        <p className="mt-1 text-xs text-text-muted">
          No leave types are available for your grade yet. Ask HR to grant an
          entitlement for your grade before applying.
        </p>
      )}
    </div>
  );
}
