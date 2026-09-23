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
  );
}