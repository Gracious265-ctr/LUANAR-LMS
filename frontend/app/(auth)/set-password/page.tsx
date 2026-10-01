"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useRef, useState } from "react";
import { Field, Input } from "@/components/ui/input";
import { Button, buttonVariants } from "@/components/ui/button";
import { FormError } from "@/components/ui/form-error";
import { Card } from "@/components/ui/card";
import { Alert } from "@/components/ui/alert";
import { confirmPasswordSet, validatePasswordSetToken } from "@/lib/password-set";

type Phase = "checking" | "ready" | "dead";

/**
 * The moment after HR's email.
 *
 * The token is read once into a ref and immediately scrubbed from the URL, so it
 * cannot leak into browser history or a referrer header. A pre-flight validates
 * it before anyone is asked to type a password, because submitting a real
 * password into a link that was never going to work is a worse experience than
 * being told the link is dead.
 */
function SetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const rawToken = searchParams.get("token") || "";
  const tokenRef = useRef(rawToken);
  const [phase, setPhase] = useState<Phase>("checking");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const token = rawToken || tokenRef.current;
    tokenRef.current = token;

    if (token && window.history.replaceState) {
      const url = new URL(window.location.href);
      url.searchParams.delete("token");
      window.history.replaceState({}, "", url.toString());
    }

    let alive = true;
    (async () => {
      const result = token ? await validatePasswordSetToken(token) : null;
      if (!alive) return;
      setPhase(token && result?.valid ? "ready" : "dead");
    })();

    return () => {
      alive = false;
    };
  }, [rawToken]);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(e.currentTarget);
    const password = String(formData.get("password") || "");
    const confirm = String(formData.get("confirm_password") || "");

    if (password !== confirm) {
      setError("Passwords do not match.");
      setLoading(false);
      return;
    }

    const result = await confirmPasswordSet(tokenRef.current, password);
    if (!result.ok) {
      setError(result.error);
      // A dead link is not a password problem, so the form goes away rather than
      // leaving someone to retype a password that was never going to be accepted.
      if (result.expired) setPhase("dead");
      setLoading(false);
      return;
    }

    setSuccess(result.detail || "Password set. You can sign in now.");
    setLoading(false);
    setTimeout(() => router.push("/login"), 1000);
  }

  if (phase === "checking") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface-page">
        <Card className="border-0 w-full max-w-md shadow-card">
          <p className="text-center text-text-secondary">Checking the link...</p>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-page">
      <Card className="border-0 w-full max-w-md shadow-card">
        <h1 className="text-xl font-semibold tracking-tight text-center text-text-primary mb-2">
          Set your password
        </h1>
        <p className="text-sm text-center text-text-secondary mb-8">
          Choose a password for the LUANAR Leave Management System.
        </p>

        {phase === "dead" && !success && (
          <div className="space-y-4">
            <Alert tone="rejected">
              This link is no longer valid. Ask HR to send a new one, or request one
              from the sign-in page.
            </Alert>
            {error && <FormError>{error}</FormError>}
            <Link
              href="/forgot-password"
              className={buttonVariants({ variant: "secondary" })}
            >
              Request a new link
            </Link>
          </div>
        )}

        {phase === "ready" && !success && (
          <form onSubmit={handleSubmit} className="space-y-4">
            <Field label="Password" htmlFor="password">
              <Input id="password" name="password" type="password" required minLength={8} />
            </Field>
            <Field label="Confirm password" htmlFor="confirm_password">
              <Input
                id="confirm_password"
                name="confirm_password"
                type="password"
                required
                minLength={8}
              />
            </Field>
            {error && <FormError>{error}</FormError>}
            <Button type="submit" variant="primary" className="w-full" loading={loading}>
              {loading ? "Setting password..." : "Set password"}
            </Button>
          </form>
        )}

        {success && (
          <div className="space-y-4 text-center">
            <Alert tone="approved">{success}</Alert>
            <Link href="/login" className={buttonVariants({ variant: "secondary" })}>
              Go to sign in
            </Link>
          </div>
        )}
      </Card>
    </div>
  );
}

export default function SetPasswordPage() {
  return (
    <Suspense>
      <SetPasswordForm />
    </Suspense>
  );
}
