"use client";

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
      <div>
        <label className="block text-sm font-medium text-text-secondary mb-1.5">
          Start Date
        </label>
        <input
          type="date"
          value={startDate}
          onChange={(e) => onStartChange(e.target.value)}
          disabled={disabled}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-1 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:bg-input-disabled"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-text-secondary mb-1.5">
          End Date
        </label>
        <input
          type="date"
          value={endDate}
          onChange={(e) => onEndChange(e.target.value)}
          disabled={disabled}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-1 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:bg-input-disabled"
        />
      </div>
    </div>
  );
}
