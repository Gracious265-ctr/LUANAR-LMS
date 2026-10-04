import Link from "next/link";

import { EditActionLink, EditIconButton } from "./edit-action-link";

import type { Department } from "@/lib/departments";

/**
 * The departments HR maintains.
 *
 * The employee and team counts are shown rather than just the name because a
 * department is only useful once something is in it — a department with zero
 * employees cannot staff an approver, and saying so on the list is the fastest
 * way to notice a half-finished configuration.
 */
export function DepartmentTable({
  departments,
  onEdit,
}: {
  departments: Department[];
  /**
   * Opens the edit overlay for this row. Omitted on hosts that still link
   * to the standalone edit route, in which case the pencil renders as a link.
   */
  onEdit?: (id: number) => void;
}) {
  if (departments.length === 0) {
    return (
      <p className="text-sm text-text-muted">
        No departments yet. Create one before building a team, because a team
        belongs to a department.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-border-default text-xs uppercase tracking-wide text-text-muted">
            <th className="px-3 py-2 font-medium">Name</th>
            <th className="px-3 py-2 font-medium">Teams</th>
            <th className="px-3 py-2 font-medium">Employees</th>
            <th className="px-3 py-2 font-medium">Status</th>
            <th className="px-3 py-2 font-medium"></th>
          </tr>
        </thead>
        <tbody>
          {departments.map((department) => (
            <tr
              key={department.id}
              className="border-b border-border-default last:border-0"
            >
              <td className="px-3 py-2 font-medium text-text-primary">
                <Link
                  href={`/dashboard/hr-admin/departments/${department.id}/edit`}
                  className="hover:text-brand-primary-hover"
                >
                  {department.name}
                </Link>
              </td>
              <td className="px-3 py-2 text-text-secondary">
                {department.team_count}
              </td>
              <td className="px-3 py-2 text-text-secondary">
                {department.employee_count}
              </td>
              <td className="px-3 py-2 text-text-secondary">
                {department.is_active ? "Active" : "Retired"}
              </td>
              <td className="px-3 py-2 text-right">
                {onEdit ? (
                  <EditIconButton
                    onClick={() => onEdit(department.id)}
                    label={`Edit ${department.name}`}
                  />
                ) : (
                  <EditActionLink
                    href={`/dashboard/hr-admin/departments/${department.id}/edit`}
                  />
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
