"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { Plus } from "lucide-react";

import type { AdminUser } from "@/lib/admin-users";
import { useOverlayParam } from "@/lib/hooks/useOverlayParam";
import { matchesSearch } from "@/lib/search";
import { AdminFormOverlay } from "@/components/hr/AdminFormOverlay";
import { AdminUserForm } from "@/components/admin/admin-user-form";
import { AdminUserTable } from "@/components/admin/admin-user-table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FilterChips } from "@/components/ui/filter-chips";
import { ListSearch } from "@/components/ui/list-search";

/** Query key for the HR-user overlay on the list page. */
export const ADMIN_USER_PARAM = "user";

/** Status narrowing for the account list. Labels avoid the row's own wording. */
const STATUS_FILTERS = [
  { value: "", label: "All accounts" },
  { value: "active", label: "Active only" },
  { value: "inactive", label: "Inactive only" },
] as const;

type StatusFilter = (typeof STATUS_FILTERS)[number]["value"];

/**
 * The HR-accounts list as a create/edit overlay.
 *
 * Edit mode resolves the account from the row already on screen rather than
 * fetching it: the row carries every field the form edits (email, both names,
 * active flag), so there is no per-record request, no loading state, and no
 * not-found fetch path — only the one case where the id in the URL matches no
 * row.
 *
 * Deactivated accounts stay in the list on purpose, so a deactivated login is
 * visible rather than silently gone. The local search and status chips narrow
 * what the table draws, but never the dataset the overlay resolves against:
 * `?user=<id>` still finds its row while a filter hides it, so the not-found
 * branch stays reachable only from a stale or hand-edited URL — and it says so
 * rather than showing a blank form.
 */
export function AdminUsersSection({ users }: { users: AdminUser[] }) {
  const router = useRouter();
  const overlay = useOverlayParam(ADMIN_USER_PARAM);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("");

  const visibleUsers = useMemo(
    () =>
      users.filter((user) => {
        if (status === "active" && !user.is_active) return false;
        if (status === "inactive" && user.is_active) return false;
        return matchesSearch(search, [
          user.full_name,
          user.first_name,
          user.last_name,
          user.email,
          user.is_active ? "active" : "inactive",
        ]);
      }),
    [search, status, users]
  );

  // Editing resolves against the whole list, not the narrowed view: a filter
  // must never turn a live `?user=<id>` deep link into a not-found.
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

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <ListSearch
          value={search}
          onChange={setSearch}
          label="Search HR users"
          placeholder="Search by name or email"
          className="w-full sm:w-72"
        />
        <FilterChips
          label="Filter HR users by status"
          options={STATUS_FILTERS}
          value={status}
          onChange={setStatus}
        />
      </div>

      <AdminUserTable
        users={visibleUsers}
        onEdit={(user) => overlay.openEdit(user.id)}
        empty={
          search || status ? (
            <p className="text-sm text-text-muted">
              No HR users match this search and status.
            </p>
          ) : undefined
        }
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
