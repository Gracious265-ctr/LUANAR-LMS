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

const CATEGORY_LABELS: Record<Employee["category"], string> = {
  academic: "Academic",
  administration: "Administration",
};

export function EmployeeTable({ employees }: { employees: Employee[] }) {
  if (employees.length === 0) {
    return (
      <EmptyState
        title="No employees found"
        description="Try adjusting your search and try again."
      />
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
                className="font-medium text-brand-primary hover:text-brand-primary-hover"
              >
                {employee.full_name || employee.email}
              </Link>
            </TableCell>
            <TableCell className="text-text-secondary">{employee.email}</TableCell>
            <TableCell className="text-text-secondary">
              {employee.department || "—"}
            </TableCell>
            <TableCell className="text-text-secondary">
              {employee.designation || "—"}
            </TableCell>
            <TableCell className="text-text-secondary">
              {CATEGORY_LABELS[employee.category] || employee.category}
            </TableCell>
            <TableCell className="text-text-secondary">{employee.grade || "—"}</TableCell>
            <TableCell>
              <span
                className={
                  employee.is_active
                    ? "inline-block rounded-full bg-brand-secondary-subtle px-2.5 py-0.5 text-xs font-medium text-brand-secondary"
                    : "inline-block rounded-full bg-surface-muted px-2.5 py-0.5 text-xs font-medium text-text-muted"
                }
              >
                {employee.is_active ? "Active" : "Inactive"}
              </span>
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