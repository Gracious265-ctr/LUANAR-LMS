"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import type { Employee, UserRole } from "@/lib/employees";
import { apiErrorMessage } from "@/lib/utils";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Field, Input } from "@/components/ui/input";
import { DatePicker } from "@/components/ui/date-picker";
import { Button, buttonVariants } from "@/components/ui/button";
import { FormError } from "@/components/ui/form-error";

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
  onSuccess,
  onCancel,
}: {
  employee?: Employee;
  endpoint: string;
  method: "POST" | "PATCH";
  gradeOptions?: string[];
  /**
   * Called with the saved employee instead of navigating, so a host overlay can
   * close and refresh in place. Omit it and the form navigates to the list
   * itself, which is what the standalone `[id]` page still relies on.
   */
  onSuccess?: (employee: Employee) => void;
  /** Replaces the cancel link when the host already knows where to go back to. */
  onCancel?: () => void;
}) {
  const router = useRouter();
  const [appointmentDate, setAppointmentDate] = useState(employee?.appointment_date ?? "");
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
          category: formData.get("category"),
          grade: formData.get("grade"),
          appointment_date: formData.get("appointment_date") || null,
          is_active: formData.get("is_active") === "on",
        }),
      });

      // Read the body once: on failure it carries the field errors, and on
      // success it is the saved record, whose id the overlay needs to tell
      // whether the new row landed in the table it just refetched.
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        setError(apiErrorMessage(data));
        return;
      }

      if (onSuccess) {
        onSuccess(data as Employee);
      } else {
        router.push("/hr-admin/employees");
        router.refresh();
      }
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
      <Field label="First name" htmlFor="first_name">
        <Input
          id="first_name"
          name="first_name"
          required
          defaultValue={employee?.first_name}
        />
      </Field>

      <Field label="Last name" htmlFor="last_name">
        <Input
          id="last_name"
          name="last_name"
          required
          defaultValue={employee?.last_name}
        />
      </Field>

      <Field label="Email" htmlFor="email">
        <Input
          id="email"
          name="email"
          type="email"
          required
          defaultValue={employee?.email}
          placeholder="name@luanar.ac.mw"
        />
      </Field>

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

      <Field label="Category" htmlFor="category">
        <Select name="category" defaultValue={employee?.category ?? "academic"}>
          <SelectTrigger id="category">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CATEGORIES.map((category) => (
              <SelectItem key={category.value} value={category.value}>
                {category.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>

      <Field
        label="Grade"
        htmlFor="grade"
        hint="Choose from configured grades or type a custom one."
      >
        <Input
          id="grade"
          name="grade"
          list={gradeOptions.length > 0 ? "grade-options" : undefined}
          defaultValue={employee?.grade}
          placeholder="Select a grade or type one"
        />
        {gradeOptions.length > 0 && (
          <>
            <datalist id="grade-options">
              {gradeOptions.map((grade) => (
                <option key={grade} value={grade} />
              ))}
            </datalist>
          </>
        )}
      </Field>

      <Field label="Date of appointment" htmlFor="appointment_date">
        <DatePicker
          id="appointment_date"
          value={appointmentDate}
          onChange={setAppointmentDate}
        />
        {/* The trigger is a <button>, so the name still has to reach FormData. */}
        <input type="hidden" name="appointment_date" value={appointmentDate} />
      </Field>

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
        <FormError className="md:col-span-2">{error}</FormError>
      )}

      <div className="flex items-center gap-3 md:col-span-2">
        <Button type="submit" variant="primary" loading={loading}>
          {loading ? "Saving..." : employee ? "Save changes" : "Create employee"}
        </Button>
        {onCancel ? (
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        ) : (
          <Link
            href="/hr-admin/employees"
            className={buttonVariants({ variant: "secondary" })}
          >
            Cancel
          </Link>
        )}
      </div>
    </form>
  );
}
