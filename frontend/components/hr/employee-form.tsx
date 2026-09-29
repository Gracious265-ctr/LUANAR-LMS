"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import type { Employee, UserRole } from "@/lib/employees";
import { apiErrorMessage } from "@/lib/utils";
import { Field, Input } from "@/components/ui/input";
import { DatePicker } from "@/components/ui/date-picker";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button, buttonVariants } from "@/components/ui/button";
import { FormError } from "@/components/ui/form-error";

const CATEGORIES: { value: string; label: string }[] = [
  { value: "academic", label: "Academic" },
  { value: "administration", label: "Administration" },
];

const ROLES: { value: UserRole; label: string }[] = [
  { value: "employee", label: "Employee" },
  { value: "supervisor", label: "Supervisor" },
  { value: "hod", label: "Head of Department" },
  { value: "dean", label: "Dean" },
  { value: "registrar", label: "Registrar" },
  { value: "dvc", label: "Deputy Vice-Chancellor" },
  { value: "hr", label: "Human Resources" },
];

export function EmployeeForm({
  employee,
  endpoint,
  method,
  gradeOptions = [],
  supervisorOptions = [],
}: {
  employee?: Employee;
  endpoint: string;
  method: "POST" | "PATCH";
  gradeOptions?: string[];
  supervisorOptions?: { id: number; full_name: string }[];
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
          role: formData.get("role"),
          designation: formData.get("designation"),
          department: formData.get("department"),
          category: formData.get("category"),
          grade: formData.get("grade"),
          supervisor: formData.get("supervisor")
            ? Number(formData.get("supervisor"))
            : null,
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

      <Field label="Role" htmlFor="role">
        <Select name="role" defaultValue={employee?.role ?? "employee"}>
          <SelectTrigger id="role">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ROLES.map((role) => (
              <SelectItem key={role.value} value={role.value}>
                {role.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>

      <Field label="Designation" htmlFor="designation">
        <Input
          id="designation"
          name="designation"
          defaultValue={employee?.designation}
          placeholder="e.g. Lecturer"
        />
      </Field>

      <Field label="Department / Faculty" htmlFor="department">
        <Input
          id="department"
          name="department"
          defaultValue={employee?.department}
          placeholder="e.g. Bunda College"
        />
      </Field>

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

      <Field
        label="Supervisor"
        htmlFor="supervisor"
        hint="Used to route the supervisor approval stage for leave day plans when the workflow requires it."
      >
        <Select
          name="supervisor"
          defaultValue={employee?.supervisor ? String(employee.supervisor) : ""}
        >
          <SelectTrigger id="supervisor">
            <SelectValue placeholder="No assigned supervisor" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">No assigned supervisor</SelectItem>
            {supervisorOptions.map((supervisor) => (
              <SelectItem key={supervisor.id} value={String(supervisor.id)}>
                {supervisor.full_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
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
        <Link
          href="/dashboard/hr-admin/employees"
          className={buttonVariants({ variant: "secondary" })}
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}