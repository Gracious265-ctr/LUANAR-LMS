"use client";

import { Moon, Sun } from "lucide-react";

import { useTheme } from "@/lib/hooks/useTheme";
import { setTheme } from "@/lib/theme";
import { Button } from "@/components/ui/button";

/**
 * Switches the dark palette defined in `context/ui-context.md` §13a.
 *
 * Icon-only at every call site. It lives in the dashboard header beside sign-out
 * and in the corner of the `(auth)` pages, and neither is a place that can spare
 * the horizontal room for a label — so the control carries its meaning in
 * `aria-label` and `title` instead, which also keeps it announced correctly
 * rather than relying on an icon a screen reader would describe as a graphic.
 */
export function ThemeToggle() {
  const theme = useTheme();
  const next = theme === "dark" ? "light" : "dark";
  const label =
    next === "dark" ? "Switch to dark theme" : "Switch to light theme";

  return (
    <Button
      type="button"
      variant="secondary"
      onClick={() => setTheme(next)}
      aria-label={label}
      title={label}
      aria-pressed={theme === "dark"}
      // `secondary` and `size-10` to match the sign-out button it sits beside in
      // the header. A `ghost` control would read as a different class of action
      // next to it, and `size="icon"` alone would give the two adjacent
      // controls a 4px height difference.
      className="size-10 shrink-0 p-0"
    >
      {theme === "dark" ? (
        <Sun className="h-4 w-4" />
      ) : (
        <Moon className="h-4 w-4" />
      )}
    </Button>
  );
}
