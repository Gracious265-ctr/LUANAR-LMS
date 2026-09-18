"use client";

import type { LeaveDocumentTemplate } from "@/lib/leave-document-template";
import { cn } from "@/lib/utils";

export function DocumentTemplatePreview({
  template,
  className,
}: {
  template: LeaveDocumentTemplate;
  className?: string;
}) {
  const header = template.header.trim();
  const intro = template.intro.trim();
  const closing = template.closing.trim();
  const footer = template.footer.trim();
  const samples = new Map(
    template.available_fields.map((field) => [field.key, field.sample])
  );

  return (
    <div
      className={cn(
        "min-h-[520px] bg-surface-page p-8 text-text-primary shadow-subtle",
        className
      )}
      aria-label="Document template preview"
    >
      {header && (
        <p className="mb-6 text-center text-sm font-semibold uppercase tracking-wide">
          {header}
        </p>
      )}

      <h3 className="mb-6 text-center text-2xl font-bold tracking-wide">
        {template.title}
      </h3>

      {intro && (
        <p className="mb-6 text-sm leading-relaxed text-text-secondary">
          {intro}
        </p>
      )}

      {template.fields.length > 0 && (
        <table className="mb-6 w-full border-collapse text-sm">
          <tbody>
            {template.fields.map((field, index) => (
              <tr key={field.key} className={index % 2 === 0 ? "bg-surface-card" : ""}>
                <td className="w-1/2 border border-border-default px-3 py-2 font-medium">
                  {field.label}
                </td>
                <td className="border border-border-default px-3 py-2">
                  {samples.get(field.key) ?? ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {closing && (
        <p className="mb-8 text-sm leading-relaxed text-text-secondary">
          {closing}
        </p>
      )}

      {template.signature_areas.length > 0 && (
        <div className="mt-10 grid grid-cols-2 gap-8">
          {template.signature_areas.map((area, index) => (
            <div key={`${area.label}-${index}`} className="text-center">
              <div className="mb-8 h-10 border-b border-border-default" />
              <p className="text-sm text-text-secondary">{area.label}</p>
            </div>
          ))}
        </div>
      )}

      {footer && (
        <p className="mt-8 text-center text-xs text-text-muted">{footer}</p>
      )}
    </div>
  );
}