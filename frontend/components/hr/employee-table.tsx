import Link from "next/link";

import type { Employee } from "@/lib/employees";
import { EditActionLink } from "./edit-action-link";

const CATEGORY_LABELS: Record<Employee["category"], string> = {
  academic: "Academic",
  administration: "Administration",
};

export function EmployeeTable({ employees }: { employees: Employee[] }) {
  if (employees.length === 0) {
    return (
      <div className="py-12 text-center text-text-muted">
        <p className="text-base font-medium text-text-primary">No employees found</p>
        <p className="mt-1 text-sm">Try adjusting your search and try again.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border-default text-left text-xs font-medium uppercase tracking-wide text-text-muted">
            <th className="py-3 pr-4">Name</th>
            <th className="py-3 pr-4">Email</th>
            <th className="py-3 pr-4">Designation</th>
            <th className="py-3 pr-4">Category</th>
            <th className="py-3 pr-4">Grade</th>
            <th className="py-3 pr-4">Team</th>
            <th className="py-3 pr-4">Status</th>
            <th className="py-3 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {employees.map((employee) => (
            <tr
              key={employee.id}
              className="border-b border-border-default transition-colors hover:bg-surface-hover"
            >
              <td className="py-3 pr-4">
                <Link
                  href={`/dashboard/hr-admin/employees/${employee.id}`}
                  className="font-medium text-brand-primary hover:text-brand-primary-hover"
                >
                  {employee.full_name || employee.email}
                </Link>
              </td>
              <td className="py-3 pr-4 text-text-secondary">{employee.email}</td>
              <td className="py-3 pr-4 text-text-secondary">
                {employee.designation || "—"}
              </td>
              <td className="py-3 pr-4 text-text-secondary">
                {CATEGORY_LABELS[employee.category] || employee.category}
              </td>
              <td className="py-3 pr-4 text-text-secondary">{employee.grade || "—"}</td>
              <td className="py-3 pr-4 text-text-secondary">
                {employee.team_name || "—"}
              </td>
              <td className="py-3 pr-4">
                <span
                  className={
                    employee.is_active
                      ? "inline-block rounded-full bg-brand-secondary-subtle px-2.5 py-0.5 text-xs font-medium text-brand-secondary"
                      : "inline-block rounded-full bg-surface-muted px-2.5 py-0.5 text-xs font-medium text-text-muted"
                  }
                >
                  {employee.is_active ? "Active" : "Inactive"}
                </span>
              </td>
              <td className="py-3 text-right">
                <EditActionLink
                  href={`/dashboard/hr-admin/employees/${employee.id}`}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}