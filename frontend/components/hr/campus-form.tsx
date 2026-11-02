"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import type { Campus, CampusInput } from "@/lib/teams";
import { createCampus, updateCampus } from "@/lib/teams-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/**
 * One campus, written.
 *
 * Used for both a new campus and an edit of an existing one: the shape of the
 * thing being written does not change when it is written a second time, and a
 * second form would only be a place for the two to drift apart. On edit the
 * code stays editable for as long as no team uses the campus — a team stores
 * the campus's id, so renaming it here is one write rather than one per team.
 */
export function CampusForm({
  campus,
  onSaved,
  returnTo = "/dashboard/hr-admin/campuses",
}: {
  campus?: Campus | null;
  /** Called after a successful save, in place of navigating away. */
  onSaved?: () => void;
  /** Where to go after saving. Empty stays on the page that was open. */
  returnTo?: string;
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const editing = Boolean(campus);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(event.currentTarget);
    const name = String(formData.get("name") || "");
    const slug = name
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "");
    const input: CampusInput = {
      name,
      code: slug || name.replace(/\s+/g, "-").toLowerCase(),
      description: String(formData.get("description") || ""),
    };

    try {
      if (editing && campus) {
        await updateCampus(campus.id, input);
      } else {
        await createCampus(input);
      }
      onSaved?.();
      if (returnTo) {
        router.push(returnTo);
      }
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "An error occurred. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label
          htmlFor="campus_name"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Name
        </label>
        <Input
          id="campus_name"
          name="name"
          required
          defaultValue={campus?.name ?? ""}
          placeholder="e.g. Main Campus"
        />
      </div>
      <div>
        <label
          htmlFor="campus_description"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Description
        </label>
        <Input
          id="campus_description"
          name="description"
          defaultValue={campus?.description ?? ""}
          placeholder="Where this campus sits"
        />
      </div>
      {error && <p className="text-sm text-status-rejected">{error}</p>}
      <div className="flex items-center gap-2">
        <Button type="submit" disabled={loading} loading={loading}>
          {editing ? "Save campus" : "Create campus"}
        </Button>
        <Button
          variant="secondary"
          onClick={() => {
            if (onSaved) {
              onSaved();
              return;
            }
            router.push(returnTo);
          }}
        >
          Cancel
        </Button>
      </div>
    </form>
  );
}
