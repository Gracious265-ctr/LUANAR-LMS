import { redirect } from "next/navigation";
import { Calendar, Clock, FileText, ShieldCheck } from "lucide-react";

import { getCurrentUser } from "@/lib/auth";
import { getLeaveSummary } from "@/lib/leave-summary";

const APPROVER_ROLES = ["supervisor", "hod", "dean", "registrar", "dvc"];

export default async function DashboardPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }

  const showApprovals = APPROVER_ROLES.includes(user.role);
  const summary = await getLeaveSummary();
  const balance = summary?.available_balance ?? null;
  const fiscalPeriod = summary?.financial_year?.label;
  const profile = summary?.profile;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-text-primary">Dashboard</h2>
        <p className="text-text-secondary">
          Welcome back, {user.full_name}
        </p>
        {profile && (
          <p className="text-sm text-text-muted mt-1">
            {[profile.grade && `Grade ${profile.grade}`, profile.department]
              .filter(Boolean)
              .join(" · ") || "No employee record on file."}
          </p>
        )}
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Available Balance"
          value={balance ?? "—"}
          subtitle={
            profile && fiscalPeriod
              ? `${fiscalPeriod} · days remaining`
              : "no financial year set"
          }
          icon={<Calendar className="w-5 h-5" />}
          variant="primary"
        />
        <StatCard
          title="Pending Applications"
          value="0"
          subtitle="awaiting review"
          icon={<Clock className="w-5 h-5" />}
          variant="pending"
        />
        {showApprovals && (
          <StatCard
            title="Awaiting My Approval"
            value="0"
            subtitle="applications"
            icon={<ShieldCheck className="w-5 h-5" />}
            variant="info"
          />
        )}
        <StatCard
          title="Upcoming Leave"
          value="0"
          subtitle="days scheduled"
          icon={<FileText className="w-5 h-5" />}
          variant="secondary"
        />
      </div>

      {/* Recent Activity */}
      <div className="bg-surface-card rounded-xl border border-border-default shadow-subtle p-6">
        <h3 className="text-lg font-semibold text-text-primary mb-4">
          Recent Activity
        </h3>
        <div className="text-center py-8 text-text-muted">
          <p>No recent activity to display.</p>
          <p className="text-sm mt-1">
            Your leave applications and approvals will appear here.
          </p>
        </div>
      </div>
    </div>
  );
}

const STAT_CARD_VARIANTS = {
  primary: "bg-brand-primary-subtle text-brand-primary",
  pending: "bg-status-pending-subtle text-status-pending",
  info: "bg-status-info-subtle text-status-info",
  secondary: "bg-brand-secondary-subtle text-brand-secondary",
} as const;

function StatCard({
  title,
  value,
  subtitle,
  icon,
  variant,
}: {
  title: string;
  value: string;
  subtitle: string;
  icon: React.ReactNode;
  variant: keyof typeof STAT_CARD_VARIANTS;
}) {
  return (
    <div className="bg-surface-card rounded-xl border border-border-default shadow-subtle p-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-text-secondary">{title}</span>
        <div className={`p-2 rounded-lg ${STAT_CARD_VARIANTS[variant]}`}>
          {icon}
        </div>
      </div>
      <div className="text-3xl font-bold text-text-primary">{value}</div>
      <p className="text-sm text-text-muted mt-1">{subtitle}</p>
    </div>
  );
}