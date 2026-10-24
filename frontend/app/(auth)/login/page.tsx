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
import { ThemeToggle } from "@/components/theme-toggle";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
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

      router.push("/");
      router.refresh();
    } catch {
      setError("An error occurred. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative min-h-screen flex items-center justify-center bg-surface-page">
      {/* The auth pages have no sidebar, so the toggle has no natural
          home and is pinned to the corner of the canvas. */}
      <div className="absolute right-4 top-4">
        <ThemeToggle />
      </div>
      <Card className="border-0">
        <div className="relative z-10 flex justify-center mb-6">

        </div>
        <h1 className="text-[24px] font-bold leading-[1.2] tracking-tight text-center text-text-heading mb-2">
          Welcome Back!
        </h1>
        <p className="text-base text-center text-text-secondary mb-8">
          LUANAR Leave Management System
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
              placeholder="Enter your email"
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

          <Button type="submit" variant="primary" className="w-full h-10 text-sm font-medium" loading={loading}>
            {loading ? "Signing in..." : "Sign In"}
          </Button>

          <div className="text-center text-sm text-text-secondary">
            <Link
              href="/forgot-password"
              className="text-sm text-text-secondary hover:text-brand-primary-gradient-start hover:underline"
            >
              Forgot Password?
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
