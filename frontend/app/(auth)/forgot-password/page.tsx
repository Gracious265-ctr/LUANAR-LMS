"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { Field, Input } from "@/components/ui/input";
import { Button, buttonVariants } from "@/components/ui/button";
import { FormError } from "@/components/ui/form-error";
import { Card } from "@/components/ui/card";
import { Alert } from "@/components/ui/alert";
import { requestPasswordSetLink } from "@/lib/password-set";
import { FadeIn } from "@/components/motion/FadeIn";

export default function ForgotPasswordPage() {
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(e.currentTarget);
    const email = String(formData.get("email") || "");

    const result = await requestPasswordSetLink(email);
    if (!result.ok) {
      setError(result.error);
      setLoading(false);
      return;
    }

    // The backend always returns 202, and never tells us whether the email
    // exists, by design. The message is the same in either case.
    setSent(true);
    setLoading(false);
  }

  return (
    <FadeIn>
      <div className="min-h-screen flex items-center justify-center bg-surface-page">
        <Card className="border-0 w-full max-w-md shadow-card">
          <h1 className="text-xl font-semibold tracking-tight text-center text-text-primary mb-2">
            Forgot your password?
          </h1>
          <p className="text-sm text-center text-text-secondary mb-8">
            Enter your email address and a set-password link will be sent to it.
          </p>

          {!sent ? (
            <form onSubmit={handleSubmit} className="space-y-4">
              <Field label="Email" htmlFor="email">
                <Input id="email" name="email" type="email" required placeholder="you@luanar.ac.mw" />
              </Field>
              {error && <FormError>{error}</FormError>}
              <Button type="submit" variant="primary" className="w-full" loading={loading}>
                {loading ? "Sending..." : "Send link"}
              </Button>
              <div className="text-center text-sm text-text-secondary">
                Remembered it?{" "}
                <Link href="/login" className="text-accent underline-offset-2 hover:underline">
                  Back to sign in
                </Link>
              </div>
            </form>
          ) : (
            <div className="space-y-4 text-center">
              <Alert tone="approved">
                If that address has an account, a set-password link is on its way.
              </Alert>
              <p className="text-sm text-text-secondary">
                Check your email for the link. It expires after 72 hours.
              </p>
              <Link href="/login" className={buttonVariants({ variant: "secondary" })}>
                Back to sign in
              </Link>
            </div>
          )}
        </Card>
      </div>
    </FadeIn>
  );
}
