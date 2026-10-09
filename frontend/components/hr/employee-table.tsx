import Link from "next/link";

import type { Employee } from "@/lib/employees";
import { EditActionLink } from "./edit-action-link";
import { EmptyState } from "@/components/ui/states";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Avatar } from "@/components/ui/Avatar";

const CATEGORY_LABELS: Record<Employee["category"], string> = {
  academic: "Academic",
  administration: "Administration",
};

export function EmployeeTable({
  employees,
  empty,
}: {
  employees: Employee[];
  /** Overrides the default empty state — the section supplies search-aware copy. */
  empty?: React.ReactNode;
}) {
  if (employees.length === 0) {
    return (
      empty ?? (
        <EmptyState
          title="No employees found"
          description="Try adjusting your search and try again."
        />
      )
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Email</TableHead>
          <TableHead>Department</TableHead>
          <TableHead>Designation</TableHead>
          <TableHead>Category</TableHead>
          <TableHead>Grade</TableHead>
          <TableHead>Team</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {employees.map((employee) => (
          <TableRow
            key={employee.id}
          >
            <TableCell>
              <Link
                href={`/dashboard/hr-admin/employees/${employee.id}`}
                className="flex items-center gap-2 font-medium text-brand-primary hover:text-brand-primary-hover"
              >
                <Avatar
                  name={employee.full_name || employee.email}
                  userId={employee.id}
                  size="sm"
                />
                {employee.full_name || employee.email}
              </Link>
            </TableCell>
            <TableCell className="text-text-secondary">{employee.email}</TableCell>
            <TableCell className="text-text-secondary">
              {employee.department_name || "—"}
            </TableCell>
            <TableCell className="text-text-secondary">
              {employee.designation || "—"}
            </TableCell>
            <TableCell className="text-text-secondary">
              {CATEGORY_LABELS[employee.category] || employee.category}
            </TableCell>
            <TableCell className="text-text-secondary">{employee.grade || "—"}</TableCell>
            <TableCell className="text-text-secondary">
              {employee.team_name || "—"}
            </TableCell>
            <TableCell>
              <Badge
                size="sm"
                tone={employee.is_active ? "info" : "muted"}
                className="font-medium"
              >
                {employee.is_active ? "Active" : "Inactive"}
              </Badge>
            </TableCell>
            <TableCell className="text-right">
              <EditActionLink
                href={`/dashboard/hr-admin/employees/${employee.id}`}
              />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}