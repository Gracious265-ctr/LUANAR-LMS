"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { FormError } from "@/components/ui/form-error";
import { changePassword } from "@/lib/password-change";

/**
 * Changing a password while already signed in.
 *
 * Three things make this form different from the set-password page, and all
 * three come from the caller already having a session:
 *
 * - the current password is asked for. The endpoint needs it, because a stolen
 *   access token on its own must not be able to take the account over, and
 *   asking here is what makes the user understand that.
 * - the confirmation is checked before the request, and a mismatch never reaches
 *   the network: retyping a field you cannot see is the most common way to get
 *   this wrong, and the round trip teaches nothing.
 * - on success the form does not return to a usable page. The change ends every
 *   session including this one, so it navigates to the sign-in page with
 *   `changed=1`, which explains the logout rather than looking like a failure.
 *
 * Errors are kept per field rather than as one banner, because a wrong current
 * password and a too-short new password need different corrections and neither
 * is about the form as a whole.
 */
export function PasswordChangeForm() {
  const router = useRouter();
  const [fieldError, setFieldError] = useState<{
    field: "current_password" | "new_password" | "confirm_password";
    message: string;
  } | null>(null);
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);

  const clearErrors = () => {
    setFieldError(null);
    setFormError("");
  };

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const currentPassword = String(form.get("current_password") || "");
    const newPassword = String(form.get("new_password") || "");
    const confirmPassword = String(form.get("confirm_password") || "");

    if (newPassword !== confirmPassword) {
      setFormError("");
      setFieldError({
        field: "confirm_password",
        message: "The two passwords do not match.",
      });
      return;
    }

    setSaving(true);
    const result = await changePassword(currentPassword, newPassword, confirmPassword);
    setSaving(false);

    if (!result.ok) {
      if (result.field) {
        setFormError("");
        setFieldError({ field: result.field, message: result.error });
      } else {
        setFieldError(null);
        setFormError(result.error);
      }
      return;
    }

    // refresh() rather than a bare push: the dashboard layout is a server
    // component that read the session we have just ended, and its cached copy
    // would otherwise still be showing a signed-in shell.
    router.push("/login?changed=1");
    router.refresh();
  };

  const currentError = fieldError?.field === "current_password" ? fieldError.message : null;
  const newError = fieldError?.field === "new_password" ? fieldError.message : null;
  const confirmError =
    fieldError?.field === "confirm_password" ? fieldError.message : null;

  return (
    <Card>
      <CardHeader title="Change your password" />
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <Field
          label="Current password"
          htmlFor="current-password"
          error={currentError}
          hint="Needed so nobody using this browser without you can change your password."
        >
          <Input
            id="current-password"
            name="current_password"
            type="password"
            autoComplete="current-password"
            required
            onChange={clearErrors}
          />
        </Field>
        <Field
          label="New password"
          htmlFor="new-password"
          error={newError}
          hint="Must be different from your current password."
        >
          <Input
            id="new-password"
            name="new_password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            onChange={clearErrors}
          />
        </Field>
        <Field
          label="Confirm new password"
          htmlFor="confirm-password"
          error={confirmError}
        >
          <Input
            id="confirm-password"
            name="confirm_password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            onChange={clearErrors}
          />
        </Field>

        <Alert tone="info">
          Changing your password signs you out everywhere, including this browser,
          and emails you a note saying it happened.
        </Alert>

        {formError && <FormError>{formError}</FormError>}

        <div className="flex items-center justify-end">
          <Button type="submit" variant="primary" loading={saving} disabled={saving}>
            {saving ? "Changing..." : "Change password"}
          </Button>
        </div>
      </form>
    </Card>
  );
}
