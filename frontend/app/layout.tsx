import { cookies } from "next/headers";
import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

import { MotionProvider } from "@/components/motion/motion-provider";
import { THEME_BOOTSTRAP_SCRIPT, THEME_COOKIE, type Theme } from "@/lib/theme";

/**
 * Inter, self-hosted from `app/fonts`.
 *
 * The build deliberately does not fetch from Google. `next/font/google`
 * downloads the files at build time, and Google now answers some of those
 * downloads with an extensionless `/l/font?kit=…` URL that Turbopack 16's font
 * replacer cannot parse, which fails the build with
 * "next/font/google queries have exactly one entry" (vercel/next.js#99114).
 * Committing the font removes the network call, so the failure cannot recur and
 * builds stay reproducible — and it is what `font-src 'self'` in next.config.ts
 * already assumes.
 *
 * One file, because Inter ships as a variable font: the single woff2 carries the
 * whole `wght` axis (100–900) for the latin subset, so 400 through 700 are real
 * instances rather than four static cuts. The declared range matches the weights
 * the product actually uses (font-normal/medium/semibold/bold).
 */
const inter = localFont({
  src: "./fonts/inter-latin.woff2",
  variable: "--font-sans",
  display: "swap",
  weight: "400 700",
});

export const metadata: Metadata = {
  title: "LUANAR Leave Management System",
  description: "Digital leave application and approval system for LUANAR",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  /**
   * The stored theme is read here so `<html>` already carries the right class in
   * the server-rendered markup. Only a *stored* choice can be honoured at this
   * point — the server has no way to see `prefers-color-scheme`, so a first
   * visitor is resolved by the inline script below instead.
   *
   * Reading a cookie opts every route out of static prerendering. That is the
   * right trade for an authenticated dashboard, where the page is personalised
   * anyway, and it is what buys the dark theme a genuinely flash-free first
   * paint rather than a light frame that snaps to dark on hydration.
   */
  const cookieStore = await cookies();
  const stored = cookieStore.get(THEME_COOKIE)?.value;
  const theme: Theme | null =
    stored === "dark" || stored === "light" ? stored : null;

  return (
    <html
      lang="en"
      // Required, not cosmetic. On a first visit there is no cookie, so the
      // server cannot know the OS preference and emits no theme class — but the
      // script below resolves `prefers-color-scheme` and adds `dark` before
      // hydration. The DOM then legitimately differs from the class React
      // expects, and React cannot "fix" it without undoing the user's OS
      // preference. Suppressing on this one element is the documented way to
      // say that the difference is intended; it applies only to `<html>`'s own
      // attributes and does not silence mismatches anywhere in the tree.
      suppressHydrationWarning
      className={[
        inter.variable,
        "h-full",
        "antialiased",
        // Absent when there is no stored choice, so the inline script can tell
        // "unresolved yet" apart from "explicitly light" and apply the OS
        // preference in that one case.
        theme ?? "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <head>
        {/*
          Runs before the body paints, and only fills in the one case the server
          could not: no stored preference yet. It bails out as soon as it finds a
          class the server already set, so it never overwrites a real choice.
        */}
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP_SCRIPT }} />
      </head>
      <body className="min-h-full flex flex-col font-sans">
        <MotionProvider>{children}</MotionProvider>
      </body>
    </html>
  );
}