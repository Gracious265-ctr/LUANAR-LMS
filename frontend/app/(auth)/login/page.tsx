"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirect = searchParams.get("redirect") || "/dashboard";
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
      <div className="w-full max-w-md p-8 bg-surface-card rounded-xl shadow-card">
        <h1 className="text-2xl font-bold text-center text-text-primary mb-2">
          LUANAR Leave Management
        </h1>
        <p className="text-sm text-center text-text-secondary mb-8">
          Sign in to your account
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="email"
              className="block text-sm font-medium text-text-primary mb-1"
            >
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              required
              className="w-full px-3 py-2 border border-input-border rounded-md bg-input-background text-text-primary placeholder:text-text-placeholder focus:outline-none focus:ring-2 focus:ring-input-ring-focus focus:border-input-border-focus"
              placeholder="your@email.luanar"
            />
          </div>

          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium text-text-primary mb-1"
            >
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              required
              className="w-full px-3 py-2 border border-input-border rounded-md bg-input-background text-text-primary placeholder:text-text-placeholder focus:outline-none focus:ring-2 focus:ring-input-ring-focus focus:border-input-border-focus"
              placeholder="Enter your password"
            />
          </div>

          {error && (
            <div className="text-sm text-status-rejected bg-status-rejected-subtle p-3 rounded-md">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 px-4 bg-button-primary text-button-primary-foreground rounded-md font-medium hover:bg-button-primary-hover focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
