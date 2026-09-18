import Link from "next/link";
import { redirect } from "next/navigation";
import { CalendarDays, CalendarRange, ClipboardList, FileText, Tags, UserCheck, Users, Workflow } from "lucide-react";

import { getCurrentUser } from "@/lib/auth";

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
        <h2 className="text-2xl font-bold text-text-primary">HR Administration</h2>
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
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 text-sm text-text-muted shadow-subtle">
        Remaining document generation (rendering real approved applications)
        and the emergency reassignment area land in later units that depend on
        active leave applications.
      </div>
    </div>
  );
}