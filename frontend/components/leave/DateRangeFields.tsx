"use client";

import { DateRangePicker } from "@/components/ui/date-picker";
import { Field } from "@/components/ui/input";

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
    <Field label="Leave dates" htmlFor="leave-dates">
      <DateRangePicker
        id="leave-dates"
        from={startDate}
        to={endDate}
        onRangeChange={(from, to) => {
          onStartChange(from);
          onEndChange(to);
        }}
        disabled={disabled}
      />
    </Field>
  );
}
