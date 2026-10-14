<<<<<<< HEAD
import { BadgeCheck } from "lucide-react";

import { formatDate } from "@/lib/approvals/format";
import type { ApprovalDetail } from "@/lib/approvals/types";

import { Card, DataRow } from "./primitives";

export function EmployeeInfoCard({ detail }: { detail: ApprovalDetail }) {
  const e = detail.employee;
  return (
    <Card title="Employee info" icon={<BadgeCheck className="h-4 w-4" />}>
      <dl className="divide-y divide-border-default">
        <DataRow label="Full name" value={e.full_name} />
        <DataRow label="Staff ID" value={e.staff_id} />
        <DataRow label="Designation" value={e.designation} />
        <DataRow label="Department" value={e.department} />
        <DataRow label="Faculty" value={e.faculty} />
        <DataRow label="Grade" value={e.grade} />
        <DataRow
          label="Date of appointment"
          value={formatDate(e.date_of_appointment)}
        />
      </dl>
    </Card>
=======
import { formatDate } from "@/lib/approvals/format";
import type { ApprovalReview } from "@/lib/approvals/types";

import { DetailRow, Panel } from "./panel";

export function EmployeeInfoCard({ data }: { data: ApprovalReview }) {
  const employee = data.employee_info;
  return (
    <Panel title="Employee information">
      <dl className="divide-y divide-border-default">
        <DetailRow label="Full name">
          <span className="font-medium">{employee.name}</span>
        </DetailRow>
        <DetailRow label="Staff ID">{employee.staff_id || "—"}</DetailRow>
        <DetailRow label="Designation">{employee.designation || "—"}</DetailRow>
        <DetailRow label="Team">{employee.team || "—"}</DetailRow>
        <DetailRow label="Faculty / School">{employee.faculty || "—"}</DetailRow>
        <DetailRow label="Grade">{employee.grade || "—"}</DetailRow>
        <DetailRow label="Category">{employee.category || "—"}</DetailRow>
        <DetailRow label="Appointment date">
          {formatDate(employee.appointment_date) || "—"}
        </DetailRow>
      </dl>
    </Panel>
>>>>>>> feature/plans-teams
  );
}