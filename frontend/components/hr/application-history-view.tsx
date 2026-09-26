import type { ApplicationDetail } from "@/lib/audit";
import type { TimelineEntry } from "@/lib/leave-history";
import { TimelineView } from "@/components/leave/timeline-view";

export function ApplicationHistoryView({
  application,
  entries = [],
}: {
  application: ApplicationDetail;
  entries?: TimelineEntry[];
}) {
  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <h3 className="text-lg font-semibold text-text-primary">
          Application summary
        </h3>
        <dl className="mt-4 grid grid-cols-1 gap-4 text-sm sm:grid-cols-2 lg:grid-cols-3">
          <SummaryRow label="Reference" value={application.reference_number} />
          <SummaryRow label="Employee" value={application.employee_name} />
          <SummaryRow label="Leave type" value={application.leave_type_name} />
          <SummaryRow
            label="Dates"
            value={
              application.start_date && application.end_date
                ? `${application.start_date} \u2192 ${application.end_date}`
                : application.start_date
            }
          />
          <SummaryRow
            label="Days"
            value={
              application.calculated_days != null
                ? `${application.calculated_days} day(s)`
                : null
            }
          />
          <SummaryRow
            label="Current approver"
            value={application.current_approver_name || "Unassigned"}
          />
          <SummaryRow
            label="Submitted"
            value={
              application.submitted_at
                ? new Date(application.submitted_at).toLocaleString()
                : null
            }
          />
        </dl>
        {application.reason && (
          <div className="mt-4 text-sm">
            <span className="font-medium text-text-primary">Reason: </span>
            <span className="text-text-secondary">{application.reason}</span>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <h3 className="mb-4 text-lg font-semibold text-text-primary">
          Documents
        </h3>
        {application.documents.length === 0 ? (
          <p className="text-sm text-text-muted">
            No supporting documents were uploaded for this application.
          </p>
        ) : (
          <ul className="space-y-2 text-sm">
            {application.documents.map((doc) => (
              <li
                key={doc.id}
                className="flex items-center justify-between rounded-md border border-border-default px-4 py-3"
              >
                <div>
                  <div className="font-medium text-text-primary">
                    {doc.file_name}
                  </div>
                  <div className="text-xs text-text-muted">
                    {doc.content_type || ""}
                    {doc.file_size ? ` \u00b7 ${doc.file_size} bytes` : ""}
                  </div>
                </div>
                <a
                  href={doc.file_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
                >
                  Open
                </a>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <h3 className="mb-4 text-lg font-semibold text-text-primary">
          Timeline
        </h3>
        <TimelineView entries={entries} />
      </div>
    </div>
  );
}

function SummaryRow({
  label,
  value,
}: {
  label: string;
  value: string | null;
}) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-text-muted">
        {label}
      </dt>
      <dd className="mt-1 font-medium text-text-primary">{value ?? "\u2014"}</dd>
    </div>
  );
}