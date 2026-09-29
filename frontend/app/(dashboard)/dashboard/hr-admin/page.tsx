import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeftRight, CalendarCheck2, CalendarDays, CalendarRange, ClipboardList, FileText, History, Tags, UserCheck, Users, Workflow } from "lucide-react";

import { getCurrentUser } from "@/lib/auth";
import { Card } from "@/components/ui/card";

export default async function HRAdminPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-text-primary">HR Administration</h2>
        <p className="text-text-secondary">
          Manage employee records and configuration for the leave management system.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Link
          href="/dashboard/hr-admin/employees"
          className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle transition-colors hover:bg-surface-hover"
        >
          <div className="mb-3 inline-flex rounded-lg bg-brand-primary-subtle p-2 text-brand-primary">
            <Users className="h-5 w-5" />
          </div>
          <h3 className="text-lg font-semibold text-text-primary">Employees</h3>
          <p className="mt-1 text-sm text-text-secondary">
            Search, create, and manage employee records.
          </p>
        </Link>
        <Link
          href="/dashboard/hr-admin/entitlements"
          className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle transition-colors hover:bg-surface-hover"
        >
          <div className="mb-3 inline-flex rounded-lg bg-brand-primary-subtle p-2 text-brand-primary">
            <CalendarRange className="h-5 w-5" />
          </div>
          <h3 className="text-lg font-semibold text-text-primary">
            Grades &amp; Entitlements
          </h3>
          <p className="mt-1 text-sm text-text-secondary">
            Configure annual leave entitlements by grade range.
          </p>
        </Link>
        <Link
          href="/dashboard/hr-admin/leave-rules"
          className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle transition-colors hover:bg-surface-hover"
        >
          <div className="mb-3 inline-flex rounded-lg bg-brand-primary-subtle p-2 text-brand-primary">
            <ClipboardList className="h-5 w-5" />
          </div>
          <h3 className="text-lg font-semibold text-text-primary">Leave Rules</h3>
          <p className="mt-1 text-sm text-text-secondary">
            Configure maximum duration, notice, eligibility, and documents per
            leave type.
          </p>
        </Link>
        <Link
          href="/dashboard/hr-admin/leave-types"
          className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle transition-colors hover:bg-surface-hover"
        >
          <div className="mb-3 inline-flex rounded-lg bg-brand-primary-subtle p-2 text-brand-primary">
            <Tags className="h-5 w-5" />
          </div>
          <h3 className="text-lg font-semibold text-text-primary">Leave Types</h3>
          <p className="mt-1 text-sm text-text-secondary">
            Maintain the registry of leave types the university offers.
          </p>
        </Link>
        <Link
          href="/dashboard/hr-admin/workflows"
          className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle transition-colors hover:bg-surface-hover"
        >
          <div className="mb-3 inline-flex rounded-lg bg-brand-primary-subtle p-2 text-brand-primary">
            <Workflow className="h-5 w-5" />
          </div>
          <h3 className="text-lg font-semibold text-text-primary">Workflows</h3>
          <p className="mt-1 text-sm text-text-secondary">
            Configure approval sequences by employee category and department.
          </p>
        </Link>
        <Link
          href="/dashboard/hr-admin/calendar"
          className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle transition-colors hover:bg-surface-hover"
        >
          <div className="mb-3 inline-flex rounded-lg bg-brand-primary-subtle p-2 text-brand-primary">
            <CalendarDays className="h-5 w-5" />
          </div>
          <h3 className="text-lg font-semibold text-text-primary">
            Financial Years &amp; Holidays
          </h3>
          <p className="mt-1 text-sm text-text-secondary">
            Configure financial years and public holidays used in leave validation.
          </p>
        </Link>
        <Link
          href="/dashboard/hr-admin/delegations"
          className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle transition-colors hover:bg-surface-hover"
        >
          <div className="mb-3 inline-flex rounded-lg bg-brand-primary-subtle p-2 text-brand-primary">
            <UserCheck className="h-5 w-5" />
          </div>
          <h3 className="text-lg font-semibold text-text-primary">Delegations</h3>
          <p className="mt-1 text-sm text-text-secondary">
            Approve delegations when approvers are unavailable, reject with a
            reason, or cancel active cover.
          </p>
        </Link>
        <Link
          href="/dashboard/hr-admin/reassignments"
          className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle transition-colors hover:bg-surface-hover"
        >
          <div className="mb-3 inline-flex rounded-lg bg-brand-primary-subtle p-2 text-brand-primary">
            <ArrowLeftRight className="h-5 w-5" />
          </div>
          <h3 className="text-lg font-semibold text-text-primary">Reassignments</h3>
          <p className="mt-1 text-sm text-text-secondary">
            Intervene on pending leave applications and reassign them to a
            replacement approver.
          </p>
        </Link>
        <Link
          href="/dashboard/hr-admin/leave-document-template"
          className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle transition-colors hover:bg-surface-hover"
        >
          <div className="mb-3 inline-flex rounded-lg bg-brand-primary-subtle p-2 text-brand-primary">
            <FileText className="h-5 w-5" />
          </div>
          <h3 className="text-lg font-semibold text-text-primary">
            Document Template
          </h3>
          <p className="mt-1 text-sm text-text-secondary">
            Configure the official template used for approved leave documents:
            wording, fields, and signature areas.
          </p>
        </Link>
        <Link
          href="/dashboard/plans/admin"
          className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle transition-colors hover:bg-surface-hover"
        >
          <div className="mb-3 inline-flex rounded-lg bg-brand-primary-subtle p-2 text-brand-primary">
            <CalendarCheck2 className="h-5 w-5" />
          </div>
          <h3 className="text-lg font-semibold text-text-primary">
            Leave Day Plans
          </h3>
          <p className="mt-1 text-sm text-text-secondary">
            Review every employee&apos;s leave day plan and the plan settings
            that govern confirmation windows.
          </p>
        </Link>
        <Link
          href="/dashboard/hr-admin/audit"
          className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle transition-colors hover:bg-surface-hover"
        >
          <div className="mb-3 inline-flex rounded-lg bg-brand-primary-subtle p-2 text-brand-primary">
            <History className="h-5 w-5" />
          </div>
          <h3 className="text-lg font-semibold text-text-primary">Audit View</h3>
          <p className="mt-1 text-sm text-text-secondary">
            Review finalized leave applications and the administrative audit
            trail of system actions.
          </p>
        </Link>
      </div>

      <Card className="text-sm text-text-muted">
        Remaining document generation (rendering real approved applications)
        lands in later units that depend on active leave applications.
      </Card>
    </div>
  );
}