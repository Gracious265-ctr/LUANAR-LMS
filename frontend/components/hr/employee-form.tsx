"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import type { Employee } from "@/lib/employees";
import { apiErrorMessage } from "@/lib/utils";

const CATEGORIES: { value: string; label: string }[] = [
  { value: "academic", label: "Academic" },
  { value: "administration", label: "Administration" },
];

export function EmployeeForm({
  employee,
  endpoint,
  method,
  gradeOptions = [],
}: {
  employee?: Employee;
  endpoint: string;
  method: "POST" | "PATCH";
  gradeOptions?: string[];
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(event.currentTarget);

    try {
      const response = await fetch(endpoint, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          first_name: formData.get("first_name"),
          last_name: formData.get("last_name"),
          email: formData.get("email"),
          designation: formData.get("designation"),
          department: formData.get("department"),
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
          Department / Faculty
        </label>
        <input
          id="department"
          name="department"
          defaultValue={employee?.department}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          placeholder="e.g. Bunda College"
        />
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