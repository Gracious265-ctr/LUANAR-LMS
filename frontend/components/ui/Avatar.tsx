import { cn } from "@/lib/utils";

/**
 * Initials avatar with a deterministic per-person colour (spec 3.2).
 *
 * The colour is a pure function of `userId`, so the same person renders the
 * same colour on every screen they appear on — the stepper, tables, the audit
 * log and the top bar all agree. Identity tints are deliberately picked from
 * pastel families that are *not* status colours: an avatar must never read as
 * a status. `src` is wired now (spec: photo support without a second pass) and
 * only renders when present; otherwise initials show.
 */
const COLORS = [
  "bg-blue-100 text-blue-700",
  "bg-emerald-100 text-emerald-700",
  "bg-amber-100 text-amber-700",
  "bg-rose-100 text-rose-700",
  "bg-violet-100 text-violet-700",
  "bg-cyan-100 text-cyan-700",
] as const;

const SIZES = {
  sm: "h-6 w-6 text-xs",
  md: "h-8 w-8 text-sm",
  lg: "h-10 w-10 text-base",
} as const;

export type AvatarSize = keyof typeof SIZES;

function colorForUser(userId: string): string {
  const hash = Array.from(userId).reduce(
    (acc, char) => acc + char.charCodeAt(0),
    0
  );
  return COLORS[hash % COLORS.length];
}

function initialsFor(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const initials = parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
  return initials || "?";
}

export interface AvatarProps extends React.HTMLAttributes<HTMLSpanElement> {
  name: string;
  /** Stable person identifier — a user/employee id, or the name when none exists. */
  userId: string | number;
  size?: AvatarSize;
  /** Profile photo; initials render while absent (the current state everywhere). */
  src?: string | null;
}

export function Avatar({
  name,
  userId,
  size = "md",
  src,
  className,
  ...props
}: AvatarProps) {
  const sizeClass = SIZES[size];

  if (src) {
    return (
      <span
        aria-hidden="true"
        {...props}
        className={cn(
          "inline-flex shrink-0 overflow-hidden rounded-full",
          sizeClass,
          className
        )}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt=""
          className="h-full w-full object-cover"
          loading="lazy"
        />
      </span>
    );
  }

  return (
    <span
      aria-hidden="true"
      {...props}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full font-medium",
        colorForUser(String(userId)),
        sizeClass,
        className
      )}
    >
      {initialsFor(name)}
    </span>
  );
}
