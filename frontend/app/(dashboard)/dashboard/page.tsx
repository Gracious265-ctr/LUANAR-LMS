import { redirect } from "next/navigation";
import { Calendar, Clock, FileText, ShieldCheck } from "lucide-react";

import { getCurrentUser } from "@/lib/auth";
import { loadApprovalCapabilities } from "@/lib/approvals/capabilities";
import { getLeaveSummary } from "@/lib/leave-summary";
import { Card } from "@/components/ui/card";
import { FadeIn } from "@/components/motion/FadeIn";
import { Stagger } from "@/components/motion/Stagger";
import { StaggerItem } from "@/components/motion/StaggerItem";

export default async function DashboardPage() {
  // All three reads are independent, and the first two are already resolved by
  // the layout above — so this costs one round trip's worth of waiting rather
  // than three in sequence.
  const [user, capabilities, summary] = await Promise.all([
    getCurrentUser(),
    loadApprovalCapabilities(),
    getLeaveSummary(),
  ]);

  if (!user) {
    redirect("/login");
  }

  // Whether the caller has anything to approve is a question about approver
  // holdings, not about the account's system role.
  const showApprovals = capabilities !== null && capabilities.is_approver;
  const pendingApprovals = capabilities?.pending_count ?? 0;
  const balance = summary?.available_balance ?? null;
  const fiscalPeriod = summary?.financial_year?.label;
  const profile = summary?.profile;
  // Applicant-side, unlike ``pendingApprovals`` above: this is what the signed-in
  // person has sent, that is what they are being asked to decide.
  const pendingApplications = summary?.pending_applications ?? 0;
  const upcomingDays = summary?.upcoming_leave?.days ?? 0;

  return (
    <FadeIn>
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-text-primary">Dashboard</h2>
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
        <Stagger className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StaggerItem>
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
          </StaggerItem>
          <StaggerItem>
            <StatCard
              title="Pending Applications"
              value={String(pendingApplications)}
              subtitle="awaiting review"
              icon={<Clock className="w-5 h-5" />}
              variant="pending"
            />
          </StaggerItem>
          {showApprovals && (
            <StaggerItem>
              <StatCard
                title="Awaiting My Approval"
                value={String(pendingApprovals)}
                subtitle="applications"
                icon={<ShieldCheck className="w-5 h-5" />}
                variant="info"
              />
            </StaggerItem>
          )}
          <StaggerItem>
            <StatCard
              title="Upcoming Leave"
              value={String(upcomingDays)}
              subtitle="days scheduled"
              icon={<FileText className="w-5 h-5" />}
              variant="secondary"
            />
          </StaggerItem>
        </Stagger>

        {/* Recent Activity */}
        <Card>
          <h3 className="text-lg font-semibold text-text-primary mb-4">
            Recent Activity
          </h3>
          <div className="text-center py-8 text-text-muted">
            <p>No recent activity to display.</p>
            <p className="text-sm mt-1">
              Your leave applications and approvals will appear here.
            </p>
          </div>
        </Card>
      </div>
    </FadeIn>
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
    <Card>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-text-secondary">{title}</span>
        <div className={`p-2 rounded-lg ${STAT_CARD_VARIANTS[variant]}`}>
          {icon}
        </div>
      </div>
      <div className="text-3xl font-semibold tracking-tight text-text-primary">{value}</div>
      <p className="text-sm text-text-muted mt-1">{subtitle}</p>
    </Card>
  );
}