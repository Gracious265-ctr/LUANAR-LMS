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

  useEffect(() => {
    getLeaveTypes().then(setTypes);
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
        disabled={disabled}
        className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-1 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:bg-input-disabled"
      >
        <option value="">Select leave type</option>
        {types.map((t) => (
          <option key={t.id} value={t.id}>
            {t.name}
          </option>
        ))}
      </select>
    </div>
  );
}
