"use client";

import { Field, Input } from "@/components/ui/input";

interface DateRangeFieldsProps {
  startDate: string;
  endDate: string;
  onStartChange: (v: string) => void;
  onEndChange: (v: string) => void;
  disabled?: boolean;
}

export function DateRangeFields({
  startDate,
  endDate,
  onStartChange,
  onEndChange,
  disabled,
}: DateRangeFieldsProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <Field label="Start Date" htmlFor="start-date">
        <Input
          id="start-date"
          type="date"
          value={startDate}
          onChange={(e) => onStartChange(e.target.value)}
          disabled={disabled}
        />
      </Field>
      <Field label="End Date" htmlFor="end-date">
        <Input
          id="end-date"
          type="date"
          value={endDate}
          onChange={(e) => onEndChange(e.target.value)}
          disabled={disabled}
        />
      </Field>
    </div>
  );
}
