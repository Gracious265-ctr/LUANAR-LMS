"use client";

import { useEffect, useState } from "react";

import { getLeaveTypes, type LeaveType } from "@/lib/services/leaveTypes";
import { Field, Select } from "@/components/ui/input";

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
    <Field label="Leave Type" htmlFor="leave-type">
      <Select
        id="leave-type"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
        disabled={disabled}
      >
        <option value="">Select leave type</option>
        {types.map((t) => (
          <option key={t.id} value={t.id}>
            {t.name}
          </option>
        ))}
      </Select>
    </Field>
  );
}
