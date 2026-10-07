import Link from "next/link";
import { redirect } from "next/navigation";
import { Plus, Search } from "lucide-react";

import { EmployeeTable } from "@/components/hr/employee-table";
import { getCurrentUser } from "@/lib/auth";
import { listEmployees } from "@/lib/employees";

export default async function EmployeesPage({
  searchParams,
}: {
  searchParams: Promise<{ search?: string | string[] }>;
}) {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  const { search } = await searchParams;
  const query = typeof search === "string" ? search : "";
  let error = "";
  let employees;

  try {
    employees = await listEmployees(query);
  } catch {
    error = "Unable to load employees. Please try again.";
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">Employees</h2>
          <p className="text-text-secondary">
            Search and manage employee records.
          </p>
        </div>
        <Link
          href="/dashboard/hr-admin/employees/new"
          className="inline-flex items-center gap-2 rounded-md bg-button-primary px-4 py-2 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover"
        >
          <Plus className="h-4 w-4" />
          New employee
        </Link>
      </div>

      <form
        method="get"
        className="flex max-w-md items-center gap-2"
      >
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
          <input
            name="search"
            defaultValue={query}
            placeholder="Search name, email, team..."
            className="w-full rounded-md border border-input-border bg-input-background py-2 pl-9 pr-3 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          />
        </div>
        <button
          type="submit"
          className="rounded-md border border-border-default bg-button-secondary px-4 py-2 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
        >
          Search
        </button>
      </form>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        {error ? (
          <div className="py-12 text-center text-sm text-status-rejected bg-status-rejected-subtle rounded-md">
            {error}
          </div>
        ) : employees ? (
          <EmployeeTable employees={employees.results} />
        ) : null}
      </div>
    </div>
  );
}