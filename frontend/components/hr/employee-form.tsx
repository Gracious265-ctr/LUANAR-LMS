"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Plus } from "lucide-react";

import type { Employee, UserRole } from "@/lib/employees";
import type { Department } from "@/lib/departments";
import { createDepartment } from "@/lib/departments-client";
import { apiErrorMessage } from "@/lib/utils";

const CATEGORIES: { value: string; label: string }[] = [
  { value: "academic", label: "Academic" },
  { value: "administration", label: "Administration" },
];

/**
 * What an account can reach, said in words.
 *
 * This is displayed, not chosen: the directory creates normal employees,
 * approver access follows from a workflow appointment, and an HR account is
 * created by an administrator. Showing the current value keeps an edit from
 * looking as though it could change it.
 */
const ROLE_LABELS: Record<UserRole, string> = {
  employee: "Employee",
  approver: "Approver",
  hr: "Human Resources",
};

export function EmployeeForm({
  employee,
  endpoint,
  method,
  gradeOptions = [],
  departments = [],
  departmentsError = "",
}: {
  employee?: Employee;
  endpoint: string;
  method: "POST" | "PATCH";
  gradeOptions?: string[];
  departments?: Department[];
  /** Set when the departments fetch failed; the picker is then shown unusable. */
  departmentsError?: string;
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  // The server-loaded options are the starting point, not the final word: HR
  // can create a department from this form, and the option they just made must
  // appear in the picker without leaving the page.
  const [departmentOptions, setDepartmentOptions] = useState<Department[]>(departments);
  const [newDepartment, setNewDepartment] = useState("");
  const [showNewDepartment, setShowNewDepartment] = useState(false);
  const [creatingDepartment, setCreatingDepartment] = useState(false);
  const [departmentCreateError, setDepartmentCreateError] = useState("");
  const [selectedDepartment, setSelectedDepartment] = useState(
    employee?.department === null || employee?.department === undefined
      ? ""
      : String(employee.department)
  );

  async function handleCreateDepartment() {
    const name = newDepartment.trim();
    if (name === "") return;
    setDepartmentCreateError("");
    setCreatingDepartment(true);
    try {
      const created = await createDepartment({ name });
      setDepartmentOptions((current) =>
        [...current, created].sort((a, b) => a.name.localeCompare(b.name))
      );
      setSelectedDepartment(String(created.id));
      setNewDepartment("");
      setShowNewDepartment(false);
    } catch (err) {
      setDepartmentCreateError(
        err instanceof Error ? err.message : "Could not create the department."
      );
    } finally {
      setCreatingDepartment(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(event.currentTarget);

    const departmentValue = String(formData.get("department") || "");

    try {
      const response = await fetch(endpoint, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          first_name: formData.get("first_name"),
          last_name: formData.get("last_name"),
          email: formData.get("email"),
          password: formData.get("password"),
          designation: formData.get("designation"),
          department: departmentValue ? Number(departmentValue) : null,
          category: formData.get("category"),
          grade: formData.get("grade"),
          appointment_date: formData.get("appointment_date") || null,
          is_active: formData.get("is_active") === "on",
        }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        setError(apiErrorMessage(data));
        return;
      }

      router.push("/dashboard/hr-admin/employees");
      router.refresh();
    } catch {
      setError("An error occurred. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="grid grid-cols-1 gap-4 md:grid-cols-2"
    >
      <div>
        <label
          htmlFor="first_name"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          First name
        </label>
        <input
          id="first_name"
          name="first_name"
          required
          defaultValue={employee?.first_name}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
      </div>

      <div>
        <label
          htmlFor="last_name"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Last name
        </label>
        <input
          id="last_name"
          name="last_name"
          required
          defaultValue={employee?.last_name}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
      </div>

      <div>
        <label
          htmlFor="email"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Email
        </label>
        <input
          id="email"
          name="email"
          type="email"
          required
          defaultValue={employee?.email}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          placeholder="name@luanar.ac.mw"
        />
      </div>

      <div>
        <label
          htmlFor="role"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Role
        </label>
        <input
          id="role"
          name="role"
          readOnly
          value={ROLE_LABELS[employee?.role ?? "employee"]}
          className="w-full cursor-not-allowed rounded-md border border-input-border bg-input-background px-3 py-2 text-text-muted focus:outline-none"
        />
        <p className="mt-1 text-xs text-text-muted">
          The directory creates normal employees. Approver access follows from
          the workflow stage you appoint somebody to, and an HR account is
          created by an administrator.
        </p>
      </div>

      <div>
        <label
          htmlFor="password"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Password
        </label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="new-password"
          required={!employee}
          minLength={8}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          placeholder={
            employee ? "Leave blank to keep the current password" : "At least 8 characters"
          }
        />
        <p className="mt-1 text-xs text-text-muted">
          {employee
            ? "Filling this in resets the password. They sign in with the new one next time."
            : "The password this person signs in with, alongside their email. You can reset it later."}
        </p>
      </div>



      <div>
        <label
          htmlFor="designation"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Designation
        </label>
        <input
          id="designation"
          name="designation"
          defaultValue={employee?.designation}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          placeholder="e.g. Lecturer"
        />
      </div>

      <div>
        <label
          htmlFor="department"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Department
        </label>
        <select
          id="department"
          name="department"
          value={selectedDepartment}
          onChange={(event) => setSelectedDepartment(event.target.value)}
          disabled={departmentsError !== ""}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-50"
        >
          <option value="">No department</option>
          {departmentOptions.map((department) => (
            <option key={department.id} value={department.id}>
              {department.name}
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-text-muted">
          {departmentsError ||
            "A pick from the departments HR maintains. It is what makes somebody eligible to approve for a team in the same department."}
        </p>
        {!showNewDepartment ? (
          <button
            type="button"
            onClick={() => setShowNewDepartment(true)}
            className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-border-default bg-button-secondary px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
          >
            <Plus className="h-4 w-4" />
            Create department
          </button>
        ) : (
          <div className="mt-2 rounded-md border border-border-default bg-surface-muted p-3">
            <div className="flex flex-wrap items-center gap-2">
              <input
                aria-label="New department name"
                value={newDepartment}
                onChange={(event) => setNewDepartment(event.target.value)}
                placeholder="e.g. ICT"
                className="min-w-40 flex-1 rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
              />
              <button
                type="button"
                onClick={() => void handleCreateDepartment()}
                disabled={creatingDepartment || newDepartment.trim() === ""}
                className="rounded-md bg-button-primary px-3 py-1.5 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
              >
                {creatingDepartment ? "Saving..." : "Save department"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowNewDepartment(false);
                  setDepartmentCreateError("");
                }}
                className="rounded-md border border-border-default bg-button-secondary px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
              >
                Cancel
              </button>
            </div>
            {departmentCreateError ? (
              <p className="mt-1 text-xs text-status-rejected">
                {departmentCreateError}
              </p>
            ) : null}
          </div>
        )}
      </div>

      <div>
        <label
          htmlFor="category"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Category
        </label>
        <select
          id="category"
          name="category"
          defaultValue={employee?.category ?? "academic"}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        >
          {CATEGORIES.map((category) => (
            <option key={category.value} value={category.value}>
              {category.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label
          htmlFor="grade"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Grade
        </label>
        <input
          id="grade"
          name="grade"
          list={gradeOptions.length > 0 ? "grade-options" : undefined}
          defaultValue={employee?.grade}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          placeholder="Select a grade or type one"
        />
        {gradeOptions.length > 0 && (
          <>
            <datalist id="grade-options">
              {gradeOptions.map((grade) => (
                <option key={grade} value={grade} />
              ))}
            </datalist>
            <p className="mt-1 text-xs text-text-muted">
              Choose from configured grades or type a custom one.
            </p>
          </>
        )}
      </div>

      <div>
        <label
          htmlFor="appointment_date"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Date of appointment
        </label>
        <input
          id="appointment_date"
          name="appointment_date"
          type="date"
          defaultValue={employee?.appointment_date ?? ""}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
      </div>

      <label className="flex items-center gap-2 md:col-span-2">
        <input
          type="checkbox"
          name="is_active"
          defaultChecked={employee?.is_active ?? true}
          className="size-4 rounded border-input-border text-brand-primary focus:ring-input-ring-focus"
        />
        <span className="text-sm font-medium text-text-primary">Active account</span>
      </label>

      {error && (
        <div className="text-sm text-status-rejected bg-status-rejected-subtle rounded-md p-3 md:col-span-2">
          {error}
        </div>
      )}

      <div className="flex items-center gap-3 md:col-span-2">
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-button-primary px-4 py-2 font-medium text-button-primary-foreground hover:bg-button-primary-hover focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Saving..." : employee ? "Save changes" : "Create employee"}
        </button>
        <Link
          href="/dashboard/hr-admin/employees"
          className="rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-text-secondary hover:bg-button-secondary-hover"
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}
