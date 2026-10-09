import Link from "next/link";

import type { AdminUser } from "@/lib/admin-users";
import { STATUS_TEXT } from "@/lib/status-styles";

/**
 * The HR accounts a superuser has created.
 *
 * Read-only except for the edit action: activation, renaming, and password
 * resets are decisions about one account and belong on that account's form, so
 * this list cannot change anything by accident. With `onEdit` the row opens the
 * overlay instead of navigating, and the action names the account because one
 * bare "Edit" per row would be indistinguishable to a screen reader.
 */
export function AdminUserTable({
  users,
  onEdit,
}: {
  users: AdminUser[];
  onEdit?: (user: AdminUser) => void;
}) {
  if (users.length === 0) {
    return (
      <p className="text-sm text-text-muted">
        No HR users yet. Create one to hand over the HR back office.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-border-default text-xs uppercase tracking-wide text-text-muted">
            <th className="px-3 py-2 font-medium">Name</th>
            <th className="px-3 py-2 font-medium">Email</th>
            <th className="px-3 py-2 font-medium">Status</th>
            <th className="px-3 py-2 font-medium">Role</th>
            <th className="px-3 py-2 font-medium"></th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr
              key={user.id}
              className="border-b border-border-default last:border-0"
            >
              <td className="px-3 py-2 font-medium text-text-primary">
                {user.full_name || "—"}
              </td>
              <td className="px-3 py-2 text-text-secondary">{user.email}</td>
              <td className="px-3 py-2">
                <span
                  className={
                    user.is_active ? STATUS_TEXT.approved : "text-text-muted"
                  }
                >
                  {user.is_active ? "Active" : "Inactive"}
                </span>
              </td>
              <td className="px-3 py-2 text-text-secondary">
                Human Resources
              </td>
              <td className="px-3 py-2 text-right">
                {onEdit ? (
                  <button
                    type="button"
                    onClick={() => onEdit(user)}
                    aria-label={`Edit ${user.full_name || user.email}`}
                    className="font-medium text-brand-primary hover:text-brand-primary-hover"
                  >
                    Edit
                  </button>
                ) : (
                  <Link
                    href={`/dashboard/admin/users/${user.id}/edit`}
                    className="font-medium text-brand-primary hover:text-brand-primary-hover"
                  >
                    Edit
                  </Link>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
