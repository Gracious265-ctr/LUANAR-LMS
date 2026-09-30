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

  useEffect(() => {
    getLeaveTypes().then(setTypes);
  }, []);

  return (
    <Field label="Leave Type" htmlFor="leave-type">
      <Select
        value={value === null || value === undefined ? "" : String(value)}
        onValueChange={(next) => onChange(next ? Number(next) : null)}
        disabled={disabled}
      >
        <SelectTrigger id="leave-type" aria-label="Leave Type">
          <SelectValue placeholder="Select leave type" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="">Select leave type</SelectItem>
          {types.map((t) => (
            <SelectItem key={t.id} value={String(t.id)}>
              {t.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </Field>
  );
}
