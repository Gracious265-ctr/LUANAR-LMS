"use client";

import type { ReactNode } from "react";
import { useState } from "react";
import { useRouter } from "next/navigation";

import { Plus, SearchX } from "lucide-react";

import type { Employee } from "@/lib/employees";
import { useOverlayParam } from "@/lib/hooks/useOverlayParam";
import { AdminFormOverlay } from "@/components/hr/AdminFormOverlay";
import { EmployeeForm } from "@/components/hr/employee-form";
import { EmployeeTable } from "@/components/hr/employee-table";
import { Alert } from "@/components/ui/alert";
import { EmptyState } from "@/components/ui/states";
import { Button } from "@/components/ui/button";

/** Query key for the employee overlay. Distinct from the `?search` list filter. */
export const EMPLOYEE_PARAM = "employee";

export interface EmployeesSectionProps {
  /** The page currently showing, not the whole staff. */
  employees: Employee[];
  /** Total across every page, so the message can say what it is hiding. */
  totalCount: number;
  gradeOptions: string[];
  /** The page's active `?search`, so the message can name it and offer to clear it. */
  search: string;
  /** The search form, passed in as a slot because the page owns the GET URLs. */
  filter?: ReactNode;
  error?: string;
}

/**
 * The employee list as a create overlay.
 *
 * The profile page stays a page: it is a record of one person with their team,
 * their grade history and their document trail, not a short form.
 *
 * The "saved but not on this page" warning here has two causes, and the copy
 * names both because they call for different actions. A new employee can be
 * missing because a `?search` is active, or because the list is one page of a
 * paginated table that has no pager — and in the second case the search is
 * innocent, so offering to clear it would be a red herring.
 */
export function EmployeesSection({
  employees,
  totalCount,
  gradeOptions,
  search,
  filter,
  error,
}: EmployeesSectionProps) {
  const router = useRouter();
  const overlay = useOverlayParam(EMPLOYEE_PARAM);
  // Decided from the list the server returns after the refresh, not from the
  // submitted values, so it cannot disagree with what is actually on screen.
  const [createdId, setCreatedId] = useState<number | null>(null);
  const createdHidden =
    createdId !== null && !employees.some((row) => row.id === createdId);

  return (
    <>
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-text-primary">Employees</h3>
          <p className="mt-1 text-sm text-text-secondary">
            {search
              ? `Showing results for "${search}".`
              : `Showing ${employees.length} of ${totalCount}.`}
          </p>
        </div>
        <Button
          variant="primary"
          onClick={overlay.openCreate}
          className="shrink-0"
        >
          <Plus className="h-4 w-4" />
          New employee
        </Button>
      </div>

      {filter}

      {createdHidden && (
        <Alert tone="info" className="mb-4 flex-col items-start">
          <p>
            Saved, but not on this page.
            {search
              ? ` This list is filtered to "${search}".`
              : ` This list shows the first ${employees.length} of ${totalCount} employees.`}
          </p>
          {search && (
            <button
              type="button"
              onClick={() => router.push("/dashboard/hr-admin/employees")}
              className="mt-2 rounded-md px-2 py-1.5 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
            >
              Clear search
            </button>
          )}
        </Alert>
      )}

      {error ? (
        <div className="rounded-lg bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
          {error}
        </div>
      ) : (
        <EmployeeTable
          employees={employees}
          empty={
            search ? (
              <EmptyState
                icon={<SearchX className="h-10 w-10" />}
                title={`No results for "${search}"`}
                description="Check the spelling, or clear the search to see everyone."
                action={
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => router.push("/dashboard/hr-admin/employees")}
                  >
                    Clear filters
                  </Button>
                }
              />
            ) : undefined
          }
        />
      )}

      <AdminFormOverlay
        open={overlay.isOpen}
        targetKey={overlay.target}
        size="md"
        title="New employee"
        description="Creating an employee also creates their sign-in account with this email address and a set password."
        onOpenChange={(open) => {
          if (!open) overlay.close();
        }}
      >
        <EmployeeForm
          endpoint="/api/hr/employees"
          method="POST"
          gradeOptions={gradeOptions}
          onSuccess={(saved) => {
            setCreatedId(saved.id);
            overlay.close();
            router.refresh();
          }}
          onCancel={overlay.close}
        />
      </AdminFormOverlay>
    </>
  );
}