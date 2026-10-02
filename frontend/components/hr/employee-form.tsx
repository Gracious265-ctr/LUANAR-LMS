"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import type { Employee, TeamOption, UserRole } from "@/lib/employees";
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

/**
 * What an account can reach. An approver position is not chosen here — it is
 * held on a team, or granted institution-wide from the Roles page — so this list
 * covers system access only.
 */
const ROLES: { value: UserRole; label: string }[] = [
  { value: "employee", label: "Employee" },
  { value: "approver", label: "Approver" },
  { value: "hr", label: "Human Resources" },
];

export function EmployeeForm({
  employee,
  endpoint,
  method,
  gradeOptions = [],
  teams = [],
  teamsError = "",
  onSuccess,
  onCancel,
}: {
  employee?: Employee;
  endpoint: string;
  method: "POST" | "PATCH";
  gradeOptions?: string[];
  teams?: TeamOption[];
  /** Set when the teams fetch failed; the picker is then shown unusable. */
  teamsError?: string;
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
    const teamValue = String(formData.get("team") || "");

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
          appointment_date: formData.get("appointment_date") || null,
          team: teamValue && teamValue !== "none" ? Number(teamValue) : null,
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
        router.push("/dashboard/hr-admin/employees");
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

<Field
        label="Team"
        htmlFor="team"
        error={teamsError || null}
        hint="Leave applications from this employee follow the team's chain. Only a team in force routes anything, so a team still being set up will not."
      >
        <Select
          name="team"
          defaultValue={String(employee?.team ?? "none")}
          disabled={teamsError !== ""}
        >
          <SelectTrigger id="team">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="none">No team</SelectItem>
            {teams.map((team) => (
              <SelectItem key={team.id} value={String(team.id)}>
                {team.name}
                {teamNote(team) ? ` (${teamNote(team)})` : ""}
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
            href="/dashboard/hr-admin/employees"
            className={buttonVariants({ variant: "secondary" })}
          >
            Cancel
          </Link>
        )}
      </div>
    </form>
  );
}
/**
 * Why a team would not route, said next to its name.
 *
 * The picker cannot simply hide a team that is not in force: an employee may
 * already belong to one, and hiding it would make them look unassigned. So
 * the team stays and the reason is spelled out, which is also the difference
 * between HR noticing now and an applicant finding out at submission.
 */
function teamNote(team: TeamOption): string {
  if (team.status === "draft") {
    return "still being set up";
  }
  if (team.status === "inactive") {
    return "retired";
  }
  if (!team.is_effective) {
    return "not in force today";
  }
  return "";
}
