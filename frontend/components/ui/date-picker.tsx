"use client";

import * as React from "react";
import { CalendarIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { fieldStyles } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  formatDateRange,
  formatDisplayDate,
  fromIsoDate,
  isDateOutsideBounds,
  toIsoDate,
} from "@/lib/date";
import { cn } from "@/lib/utils";

const TRIGGER_STYLES = [
  "w-full justify-start font-normal",
  "data-[placeholder=true]:text-text-placeholder",
] as const;

interface DatePickerProps {
  /** Associates the trigger with a `Field` label. */
  id?: string;
  /** Current date as `yyyy-MM-dd`; empty or undefined renders the placeholder. */
  value?: string;
  onChange: (iso: string) => void;
  placeholder?: string;
  min?: string;
  max?: string;
  disabled?: boolean;
  className?: string;
}

export function DatePicker({
  id,
  value,
  onChange,
  placeholder = "Select date",
  min,
  max,
  disabled,
  className,
}: DatePickerProps) {
  const [open, setOpen] = React.useState(false);
  const selected = fromIsoDate(value);
  const isDayDisabled = React.useCallback(
    (day: Date) => isDateOutsideBounds(day, min, max),
    [min, max]
  );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          variant="secondary"
          disabled={disabled}
          data-placeholder={selected ? undefined : true}
          className={cn(fieldStyles, TRIGGER_STYLES, className)}
        >
          <CalendarIcon className="h-4 w-4 opacity-70" aria-hidden="true" />
          {selected ? formatDisplayDate(value) : placeholder}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          captionLayout="dropdown"
          selected={selected}
          disabled={isDayDisabled}
          onSelect={(date) => {
            onChange(date ? toIsoDate(date) : "");
            setOpen(false);
          }}
        />
      </PopoverContent>
    </Popover>
  );
}

interface DateRangePickerProps {
  id?: string;
  from?: string;
  to?: string;
  onRangeChange: (from: string, to: string) => void;
  placeholder?: string;
  min?: string;
  max?: string;
  disabled?: boolean;
  className?: string;
}

export function DateRangePicker({
  id,
  from,
  to,
  onRangeChange,
  placeholder = "Select date range",
  min,
  max,
  disabled,
  className,
}: DateRangePickerProps) {
  const [open, setOpen] = React.useState(false);
  const [pendingFrom, setPendingFrom] = React.useState<Date | undefined>();
  const label = formatDateRange(from, to);
  const isDayDisabled = React.useCallback(
    (day: Date) => isDateOutsideBounds(day, min, max),
    [min, max]
  );

  return (
    <Popover
      open={open}
      onOpenChange={(nextOpen) => {
        setOpen(nextOpen);
        if (!nextOpen) setPendingFrom(undefined);
      }}
    >
      <PopoverTrigger asChild>
        <Button
          id={id}
          variant="secondary"
          disabled={disabled}
          data-placeholder={label ? undefined : true}
          className={cn(fieldStyles, TRIGGER_STYLES, className)}
        >
          <CalendarIcon className="h-4 w-4 opacity-70" aria-hidden="true" />
          {label || placeholder}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="range"
          captionLayout="dropdown"
          selected={
            pendingFrom
              ? { from: pendingFrom, to: undefined }
              : { from: fromIsoDate(from), to: fromIsoDate(to) }
          }
          disabled={isDayDisabled}
          onSelect={(_range, day) => {
            if (!day) {
              setPendingFrom(undefined);
              onRangeChange("", "");
              return;
            }
            if (!pendingFrom) {
              setPendingFrom(day);
              onRangeChange(toIsoDate(day), "");
              return;
            }
            setPendingFrom(undefined);
            onRangeChange(
              toIsoDate(new Date(Math.min(day.getTime(), pendingFrom.getTime()))),
              toIsoDate(new Date(Math.max(day.getTime(), pendingFrom.getTime())))
            );
            setOpen(false);
          }}
        />
      </PopoverContent>
    </Popover>
  );
}
