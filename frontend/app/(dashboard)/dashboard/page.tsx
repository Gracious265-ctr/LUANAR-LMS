import { redirect } from "next/navigation";
import { Calendar, Clock, FileText, ShieldCheck } from "lucide-react";

import type { Capabilities } from "@/lib/approvals/types";
import { apiClient } from "@/lib/api-client";
import { getCurrentUser } from "@/lib/auth";
import {
  formatIsoDate,
  getLeaveOverview,
  type LeaveOverview,
} from "@/lib/leave-overview";

const APPROVER_ROLES = ["supervisor", "hod", "dean", "registrar", "dvc"];

export default async function DashboardPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }

  const showApprovals = APPROVER_ROLES.includes(user.role);
  const [overview, capabilities] = await Promise.all([
    safeGetOverview(),
    showApprovals ? safeGetCapabilities() : Promise.resolve(null),
  ]);

  return (
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
          value={overview?.available == null ? "—" : String(overview.available)}
          subtitle="days remaining"
          icon={<Calendar className="w-5 h-5" />}
          variant="primary"
        />
        <StatCard
          title="Pending Applications"
          value={String(overview?.pending_applications ?? 0)}
          subtitle="awaiting review"
          icon={<Clock className="w-5 h-5" />}
          variant="pending"
        />
        {showApprovals && (
          <StatCard
            title="Awaiting My Approval"
            value={String(capabilities?.pending_count ?? 0)}
            subtitle="applications"
            icon={<ShieldCheck className="w-5 h-5" />}
            variant="info"
          />
        )}
        <StatCard
          title="Upcoming Leave"
          value={String(overview?.upcoming_leaves ?? 0)}
          subtitle="applications"
          icon={<FileText className="w-5 h-5" />}
          variant="secondary"
        />
      </div>

      {/* Employee Record */}
      <div className="bg-surface-card rounded-xl border border-border-default shadow-subtle p-6">
        <h3 className="text-lg font-semibold text-text-primary mb-4">
          My Employee Record
        </h3>
        {overview?.profile ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <ProfileField label="Grade" value={overview.profile.grade} />
            <ProfileField
              label="Designation"
              value={overview.profile.designation || "—"}
            />
            <ProfileField
              label="Department"
              value={overview.profile.department || "—"}
            />
            <ProfileField
              label="Category"
              value={readableCategory(overview.profile.category)}
            />
            <ProfileField
              label="Gender"
              value={readableGender(overview.profile.gender)}
            />
            <ProfileField
              label="Appointment date"
              value={formatIsoDate(overview.profile.appointment_date)}
            />
            <ProfileField
              label="Financial year"
              value={overview.financial_year?.label ?? "—"}
            />
            <ProfileField
              label="Annual entitlement"
              value={
                overview.entitlement == null
                  ? "—"
                  : `${overview.entitlement} days`
              }
            />
            <ProfileField
              label="Used this year"
              value={overview.used == null ? "—" : `${overview.used} days`}
            />
          </div>
        ) : (
          <p className="text-sm text-text-muted">
            No employee record has been configured for your account yet. Contact
            Human Resources to set up your profile.
          </p>
        )}
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

async function safeGetOverview(): Promise<LeaveOverview | null> {
  try {
    return await getLeaveOverview();
  } catch {
    return null;
  }
}

async function safeGetCapabilities(): Promise<Capabilities | null> {
  try {
    return await apiClient<Capabilities>("/api/v1/approvals/capabilities/");
  } catch {
    return null;
  }
}

function readableCategory(category: string): string {
  if (category === "academic") return "Academic";
  if (category === "administration") return "Administration";
  return category;
}

function readableGender(gender: string): string {
  if (gender === "M") return "Male";
  if (gender === "F") return "Female";
  return gender || "—";
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

function ProfileField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-medium text-text-secondary mb-1">{label}</p>
      <p className="text-sm text-text-primary">{value}</p>
    </div>
  );
}