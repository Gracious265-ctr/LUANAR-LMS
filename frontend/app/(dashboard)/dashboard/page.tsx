import { redirect } from "next/navigation";
import Link from "next/link";
import { Calendar, Clock, FileText, ShieldCheck } from "lucide-react";

import type { Capabilities } from "@/lib/approvals/types";
import { apiClient } from "@/lib/api-client";
import { getCurrentUser } from "@/lib/auth";
<<<<<<< HEAD
import type {
  ApplicationTimeline,
  TimelineEntry,
} from "@/lib/leave-history";
import {
  getMyLeaveHistory,
  type TimelineApplication,
} from "@/lib/leave-history";
import { TimelineGlyph } from "@/components/leave/timeline-view";
import { formatDateTime } from "@/lib/tracking/format";
import {
  formatIsoDate,
  getLeaveOverview,
  type LeaveOverview,
} from "@/lib/leave-overview";

const APPROVER_ROLES = ["supervisor", "hod", "dean", "registrar", "dvc"];
=======
import { loadApprovalCapabilities } from "@/lib/approvals/capabilities";
import { getLeaveSummary } from "@/lib/leave-summary";
import { Card } from "@/components/ui/card";
import { STATUS_STYLES } from "@/lib/status-styles";
import { FadeIn } from "@/components/motion/FadeIn";
import { Stagger } from "@/components/motion/Stagger";
import { StaggerItem } from "@/components/motion/StaggerItem";
>>>>>>> feature/plans-teams

interface RecentItem {
  application: TimelineApplication;
  entry: TimelineEntry;
}

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

<<<<<<< HEAD
  const showApprovals = APPROVER_ROLES.includes(user.role);
  const [overview, capabilities, recent] = await Promise.all([
    safeGetOverview(),
    showApprovals ? safeGetCapabilities() : Promise.resolve(null),
    safeGetRecentActivity(),
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
        {recent.length === 0 ? (
=======
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
>>>>>>> feature/plans-teams
          <div className="text-center py-8 text-text-muted">
            <p>No recent activity to display.</p>
            <p className="text-sm mt-1">
              Your leave applications and approvals will appear here.
            </p>
          </div>
<<<<<<< HEAD
        ) : (
          <ol className="space-y-4">
            {recent.map((item) => (
              <li
                key={`${item.application.id}:${item.entry.id}`}
                className="flex gap-3"
              >
                <span className="mt-0.5 shrink-0">
                  <TimelineGlyph kind={item.entry.kind} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                    <p className="text-sm font-medium text-text-primary">
                      {item.entry.action_label}
                    </p>
                    <span className="text-xs text-text-muted">
                      {formatDateTime(item.entry.occurred_at)}
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs text-text-muted">
                    <Link
                      href={`/applications/${item.application.id}`}
                      className="font-medium text-brand-primary hover:text-brand-primary-hover"
                    >
                      {item.application.reference_number ||
                        "#" + item.application.id.slice(0, 8)}
                    </Link>
                    {item.entry.summary ? ` · ${item.entry.summary}` : ""}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}
=======
        </Card>
>>>>>>> feature/plans-teams
      </div>
    </FadeIn>
  );
}

/**
 * The employee's own most recent timeline activity (Unit 24). Flattens every
 * application's timeline, keeps the newest eight entries, and drops
 * applications whose trails are empty.
 */
async function safeGetRecentActivity(): Promise<RecentItem[]> {
  let histories: ApplicationTimeline[];
  try {
    histories = await getMyLeaveHistory();
  } catch {
    return [];
  }
  const items: RecentItem[] = [];
  for (const history of histories) {
    for (const entry of history.entries) {
      items.push({ application: history.application, entry });
    }
  }
  items.sort(
    (a, b) =>
      new Date(b.entry.occurred_at).getTime() -
      new Date(a.entry.occurred_at).getTime()
  );
  return items.slice(0, 8);
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
  pending: STATUS_STYLES.pending,
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

function ProfileField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-medium text-text-secondary mb-1">{label}</p>
      <p className="text-sm text-text-primary">{value}</p>
    </div>
  );
}