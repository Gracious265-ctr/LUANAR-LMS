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
        <DetailRow label="Department">{employee.department || "—"}</DetailRow>
        <DetailRow label="Faculty / School">{employee.faculty || "—"}</DetailRow>
        <DetailRow label="Grade">{employee.grade || "—"}</DetailRow>
        <DetailRow label="Category">{employee.category || "—"}</DetailRow>
        <DetailRow label="Appointment date">
          {formatDate(employee.appointment_date) || "—"}
        </DetailRow>
      </dl>
    </Panel>
  );
}