"use client";

import { useRouter } from "next/navigation";

import { Plus } from "lucide-react";

import type { AdminUser } from "@/lib/admin-users";
import { useOverlayParam } from "@/lib/hooks/useOverlayParam";
import { AdminFormOverlay } from "@/components/hr/AdminFormOverlay";
import { AdminUserForm } from "@/components/admin/admin-user-form";
import { AdminUserTable } from "@/components/admin/admin-user-table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

/** Query key for the HR-user overlay on the list page. */
export const ADMIN_USER_PARAM = "user";

/**
 * The HR-accounts list as a create/edit overlay.
 *
 * Edit mode resolves the account from the row already on screen rather than
 * fetching it: the row carries every field the form edits (email, both names,
 * active flag), so there is no per-record request, no loading state, and no
 * not-found fetch path — only the one case where the id in the URL matches no
 * row.
 *
 * The list is not filtered, and deactivated accounts stay on it on purpose, so
 * a row that exists is always on screen; the not-found branch is reachable only
 * from a stale or hand-edited URL, and it says so rather than showing a blank
 * form.
 */
export function AdminUsersSection({ users }: { users: AdminUser[] }) {
  const router = useRouter();
  const overlay = useOverlayParam(ADMIN_USER_PARAM);

  const editing =
    overlay.target !== null && !overlay.isCreate
      ? users.find((row) => String(row.id) === overlay.target)
      : undefined;

  return (
    <Card>
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-text-primary">HR users</h3>
          <p className="mt-1 text-sm text-text-secondary">
            Active and inactive accounts alike, so a deactivated login stays
            visible instead of silently gone.
          </p>
        </div>
        <Button
          variant="primary"
          onClick={overlay.openCreate}
          className="shrink-0"
        >
          <Plus className="h-4 w-4" />
          New HR user
        </Button>
      </div>

      <AdminUserTable
        users={users}
        onEdit={(user) => overlay.openEdit(user.id)}
      />

      <AdminFormOverlay
        open={overlay.isOpen}
        targetKey={overlay.target}
        title={
          editing
            ? `Edit ${editing.full_name || editing.email}`
            : overlay.isCreate
              ? "New HR user"
              : "Edit HR user"
        }
        description={
          editing
            ? "Rename the account, reset its password, or deactivate it."
            : "Create an account that can administer leave. It is created with the Human Resources role and signs in with the email and password you set."
        }
        size="md"
        onOpenChange={(open) => {
          if (!open) overlay.close();
        }}
        notFound={
          editing === undefined && !overlay.isCreate
            ? "That HR user is no longer in the list."
            : undefined
        }
      >
        <AdminUserForm
          user={editing}
          onSuccess={() => {
            overlay.close();
            router.refresh();
          }}
          onCancel={overlay.close}
        />
      </AdminFormOverlay>
    </Card>
  );
}
