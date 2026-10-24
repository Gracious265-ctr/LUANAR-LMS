import { redirect } from "next/navigation";
import { Calendar, Clock, FileText, ShieldCheck } from "lucide-react";

import { getCurrentUser } from "@/lib/auth";
import { loadApprovalCapabilities } from "@/lib/approvals/capabilities";
import { getLeaveSummary } from "@/lib/leave-summary";
import { Card, CardHeader } from "@/components/ui/card";
import { StatCard } from "@/components/ui/stat-card";
import { FadeIn } from "@/components/motion/FadeIn";
import { Stagger } from "@/components/motion/Stagger";
import { StaggerItem } from "@/components/motion/StaggerItem";

export default async function DashboardPage() {
  const [user, capabilities, summary] = await Promise.all([
    getCurrentUser(),
    loadApprovalCapabilities(),
    getLeaveSummary(),
  ]);

  if (!user) {
    redirect("/login");
  }

  const showApprovals = capabilities !== null && capabilities.is_approver;
  const pendingApprovals = capabilities?.pending_count ?? 0;
  const balance = summary?.available_balance ?? null;
  const fiscalPeriod = summary?.financial_year?.label;
  const profile = summary?.profile;
  const pendingApplications = summary?.pending_applications ?? 0;
  const upcomingDays = summary?.upcoming_leave?.days ?? 0;

  return (
    <FadeIn>
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold tracking-tight text-text-primary md:text-3xl">
            Dashboard
          </h1>
          <p className="text-text-secondary">
            Welcome back, {user.full_name}
          </p>
          {(pendingApprovals > 0 || pendingApplications > 0) && (
            <p className="text-sm text-text-muted">
              {pendingApprovals > 0 && pendingApplications > 0
                ? `You have ${pendingApprovals} approval${pendingApprovals === 1 ? "" : "s"} pending and ${pendingApplications} application${pendingApplications === 1 ? "" : "s"} awaiting review.`
                : pendingApprovals > 0
                ? `You have ${pendingApprovals} approval${pendingApprovals === 1 ? "" : "s"} awaiting your review.`
                : `You have ${pendingApplications} application${pendingApplications === 1 ? "" : "s"} awaiting review.`}
            </p>
          )}
          {profile && (
            <p className="text-sm text-text-muted">
              {[profile.grade && `Grade ${profile.grade}`, profile.team]
                .filter(Boolean)
                .join(" · ") || "No employee record on file."}
            </p>
          )}
        </div>

        <Stagger className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <StaggerItem>
            <StatCard
              title="Available Balance"
              value={balance ?? "—"}
              subtitle={
                profile && fiscalPeriod
                  ? `${fiscalPeriod} · days remaining`
                  : "no financial year set"
              }
              icon={<Calendar className="h-5 w-5" />}
              variant="primary"
            />
          </StaggerItem>
          <StaggerItem>
            <StatCard
              title="Pending Applications"
              value={String(pendingApplications)}
              subtitle="awaiting review"
              icon={<Clock className="h-5 w-5" />}
              variant="pending"
              onClick={() => {
                window.location.href = "/dashboard/leave";
              }}
            />
          </StaggerItem>
          {showApprovals && (
            <StaggerItem>
              <StatCard
                title="Awaiting My Approval"
                value={String(pendingApprovals)}
                subtitle="applications"
                icon={<ShieldCheck className="h-5 w-5" />}
                variant="info"
                onClick={() => {
                  window.location.href = "/dashboard/approvals";
                }}
              />
            </StaggerItem>
          )}
          <StaggerItem>
            <StatCard
              title="Upcoming Leave"
              value={String(upcomingDays)}
              subtitle="days scheduled"
              icon={<FileText className="h-5 w-5" />}
              variant="secondary"
            />
          </StaggerItem>
        </Stagger>

        <Card>
          <CardHeader title="Recent Activity" />
          <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
            <p className="text-sm font-medium text-text-primary">No recent activity yet</p>
            <p className="text-sm text-text-muted">
              Start by submitting a leave application or checking your balance.
            </p>
            <div className="pt-2">
              <a
                href="/dashboard/leave/drafts?compose=1"
                className="inline-flex items-center justify-center rounded-sm border border-transparent bg-[linear-gradient(135deg,var(--brand-primary-gradient-start)_0%,var(--brand-primary-gradient-end)_100%)] px-4 py-2 text-sm font-medium text-white transition-all duration-base ease-standard hover:-translate-y-px hover:shadow-hover focus-ring disabled:cursor-not-allowed disabled:opacity-60 disabled:transform-none"
              >
                New Application
              </a>
            </div>
          </div>
        </Card>
      </div>
    </FadeIn>
  );
}
