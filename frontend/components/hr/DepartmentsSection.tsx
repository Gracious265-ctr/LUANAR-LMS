"use client";

import { useRouter } from "next/navigation";

import { Plus } from "lucide-react";

import type { Department } from "@/lib/departments";
import { useOverlayParam } from "@/lib/hooks/useOverlayParam";
import { AdminFormOverlay } from "@/components/hr/AdminFormOverlay";
import { DepartmentForm } from "@/components/hr/department-form";
import { DepartmentTable } from "@/components/hr/department-table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

/** Query key for the department overlay on the list page. */
export const DEPARTMENT_PARAM = "department";

/**
 * The departments registry as a create/edit overlay.
 *
 * Edit mode resolves the record from the rows already on screen rather than
 * fetching it: the row holds the name and both counts, which is everything the
 * form shows. So there is no per-record request, no loading state, and no
 * not-found fetch path — only the one case where the id in the URL matches no
 * row.
 *
 * The list carries no filter and asks for retired rows too, so a row that exists
 * is always on screen; the not-found branch is reachable only from a stale or
 * hand-edited URL, and it says so rather than showing a blank form.
 */
export function DepartmentsSection({ departments }: { departments: Department[] }) {
  const router = useRouter();
  const overlay = useOverlayParam(DEPARTMENT_PARAM);

  const editing =
    overlay.target !== null && !overlay.isCreate
      ? departments.find((row) => String(row.id) === overlay.target)
      : undefined;

  return (
    <Card>
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-text-primary">
            Departments
          </h3>
          <p className="mt-1 text-sm text-text-secondary">
            The units your teams and employees belong to. A department scopes a
            team&apos;s approvers: only its own employees may hold a stage on
            one of its teams.
          </p>
        </div>
        <Button
          variant="primary"
          onClick={overlay.openCreate}
          className="shrink-0"
        >
          <Plus className="h-4 w-4" />
          New department
        </Button>
      </div>

      <DepartmentTable departments={departments} onEdit={overlay.openEdit} />

      <AdminFormOverlay
        open={overlay.isOpen}
        targetKey={overlay.target}
        title={
          editing
            ? `Edit ${editing.name}`
            : overlay.isCreate
              ? "New department"
              : "Edit department"
        }
        description={
          editing
            ? "Rename the department, or retire it once nothing uses it."
            : "A department is what scopes a team's approvers: only its own employees may hold a stage on one of its teams."
        }
        onOpenChange={(open) => {
          if (!open) overlay.close();
        }}
        notFound={
          editing === undefined && !overlay.isCreate
            ? "That department is no longer in the list. It may have been retired and removed."
            : undefined
        }
      >
        <DepartmentForm
          department={editing}
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