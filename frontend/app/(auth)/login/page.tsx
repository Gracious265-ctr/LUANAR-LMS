"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";
import { Field, Input } from "@/components/ui/input";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { FormError } from "@/components/ui/form-error";
import { Card } from "@/components/ui/card";
import { FadeIn } from "@/components/motion/FadeIn";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirect = searchParams.get("redirect") || "/dashboard";
  // Set by the account page after a successful change, which signs the caller
  // out here. Without it this screen looks like an unexplained logout; the
  // point of a password change is that somebody watching for the consequences
  // should be told, and this is the only place the user is guaranteed to read.
  const justChanged = searchParams.get("changed") === "1";
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(e.currentTarget);

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: formData.get("email"),
          password: formData.get("password"),
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        setError(data.detail || "Login failed");
        return;
      }

      router.push(redirect);
      router.refresh();
    } catch {
      setError("An error occurred. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-page">
      <Card className="border-0 w-full max-w-md shadow-card">
        <h1 className="text-xl font-semibold tracking-tight text-center text-text-primary mb-2">
          LUANAR Leave Management
        </h1>
        <p className="text-sm text-center text-text-secondary mb-8">
          Sign in to your account
        </p>

        {justChanged && (
          <div className="mb-6">
            <Alert tone="approved">
              Your password was changed and every session was signed out. Sign in
              again with your new password.
            </Alert>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <Field label="Email" htmlFor="email">
            <Input
              id="email"
              name="email"
              type="email"
              required
              placeholder="your@email.luanar"
            />
          </Field>

          <Field label="Password" htmlFor="password">
            <Input
              id="password"
              name="password"
              type="password"
              required
              placeholder="Enter your password"
            />
          </Field>

          {error && (
            <FormError>{error}</FormError>
          )}

          <Button type="submit" variant="primary" className="w-full" loading={loading}>
            {loading ? "Signing in..." : "Sign in"}
          </Button>

          <div className="text-center text-sm text-text-secondary">
            <Link
              href="/forgot-password"
              className="text-accent underline-offset-2 hover:underline"
            >
              Forgotten your password?
            </Link>
          </div>
        </form>
      </Card>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <FadeIn>
        <LoginForm />
      </FadeIn>
    </Suspense>
  );
}
