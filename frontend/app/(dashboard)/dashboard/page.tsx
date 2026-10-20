import { redirect } from "next/navigation";
import { Calendar, Clock, FileText, ShieldCheck } from "lucide-react";

import { getCurrentUser } from "@/lib/auth";
import { loadApprovalCapabilities } from "@/lib/approvals/capabilities";
import { getLeaveSummary } from "@/lib/leave-summary";
import { Card } from "@/components/ui/card";
import { StatCard } from "@/components/ui/stat-card";
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
  // Days carried into this year by a rejected-leave rollover. The available
  // balance already includes them; this line tells the employee how much of it
  // is carry-over rather than ordinary entitlement.
  const carryOverDays = Number(summary?.carry_over_days ?? 0);
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
              {[profile.grade && `Grade ${profile.grade}`, profile.team]
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
                <>
                  <span className="block">
                    {profile && fiscalPeriod
                      ? `${fiscalPeriod} · days remaining`
                      : "no financial year set"}
                  </span>
                  {carryOverDays > 0 && (
                    <span className="block text-text-secondary">
                      Includes {carryOverDays} carried-over day
                      {carryOverDays === 1 ? "" : "s"}
                    </span>
                  )}
                </>
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

