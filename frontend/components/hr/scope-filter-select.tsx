"use client";

import { useRouter } from "next/navigation";

/**
 * A filter that is really a navigation.
 *
 * The approver screen is server-rendered — every read happens before the page
 * is drawn — so a choice here cannot be local state. It rewrites the URL, and
 * the server reads the new parameter, which is also what makes the filtered
 * view linkable and what the back button does the right thing with.
 */
export function ScopeFilterSelect({
  id,
  label,
  value,
  options,
  param,
  scope,
  clearLabel,
}: {
  id: string;
  label: string;
  /** The currently chosen option, or null for "every…". */
  value: number | null;
  options: { id: number; name: string }[];
  /** The query parameter this choice is written to. */
  param: "team" | "campus";
  /** The scope this filter belongs to, so the URL keeps its shape. */
  scope: string;
  clearLabel: string;
}) {
  const router = useRouter();

  function goTo(next: string) {
    router.push(`/dashboard/hr-admin/approvers?scope=${scope}${next}`);
  }

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <label htmlFor={id} className="text-text-secondary">
        {label}
      </label>
      <select
        id={id}
        value={value === null ? "" : String(value)}
        onChange={(event) => {
          const next = event.target.value;
          goTo(next ? `&${param}=${next}` : "");
        }}
        className="rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
      >
        <option value="">Every {label.toLowerCase().replace(":", "")}</option>
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.name}
          </option>
        ))}
      </select>
      {value !== null && (
        <button
          type="button"
          onClick={() => goTo("")}
          className="text-xs font-medium text-brand-primary hover:text-brand-primary-hover"
        >
          {clearLabel}
        </button>
      )}
    </div>
  );
}
