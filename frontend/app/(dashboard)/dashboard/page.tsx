import { redirect } from "next/navigation";
import { Calendar, Clock, FileText, ShieldCheck } from "lucide-react";

import { DashboardShell } from "@/components/dashboard/dashboard-shell";
import { getCurrentUser } from "@/lib/auth";

const APPROVER_ROLES = ["supervisor", "hod", "dean", "registrar", "dvc"];

export default async function DashboardPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }

  const showApprovals = APPROVER_ROLES.includes(user.role);

  return (
    <DashboardShell user={user}>
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">Dashboard</h2>
          <p className="text-text-secondary">
            Welcome back, {user.full_name}
          </p>
        </div>

        {/* Stat Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Available Balance"
            value="21"
            subtitle="days remaining"
            icon={<Calendar className="w-5 h-5" />}
            color="brand-primary"
          />
          <StatCard
            title="Pending Applications"
            value="0"
            subtitle="awaiting review"
            icon={<Clock className="w-5 h-5" />}
            color="status-pending"
          />
          {showApprovals && (
            <StatCard
              title="Awaiting My Approval"
              value="0"
              subtitle="applications"
              icon={<ShieldCheck className="w-5 h-5" />}
              color="status-info"
            />
          )}
          <StatCard
            title="Upcoming Leave"
            value="0"
            subtitle="days scheduled"
            icon={<FileText className="w-5 h-5" />}
            color="brand-secondary"
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
    </DashboardShell>
  );
}

function StatCard({
  title,
  value,
  subtitle,
  icon,
  color,
}: {
  title: string;
  value: string;
  subtitle: string;
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <div className="bg-surface-card rounded-xl border border-border-default shadow-subtle p-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-text-secondary">{title}</span>
        <div
          className={`p-2 rounded-lg bg-${color}-subtle text-${color}`}
        >
          {icon}
        </div>
      </div>
      <div className="text-3xl font-bold text-text-primary">{value}</div>
      <p className="text-sm text-text-muted mt-1">{subtitle}</p>
    </div>
  );
}
