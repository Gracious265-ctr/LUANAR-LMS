import type { CalendarLeaveTypeRef } from "./types";

/**
 * Deterministic per-leave-type tint for the calendar bars (spec 3.1).
 *
 * There is no leave-type colour column in the registry, so the tint is derived
 * from the type's stable key — the same type keeps the same colour on every
 * row and every month. The families are deliberately the pastel avatar
 * families, not status colours: a bar is a leave *type*, and must never read
 * as an approval status.
 *
 * Hex fills (not Tailwind classes) because a pending bar is hatched with a
 * `repeating-linear-gradient`, which needs a colour value it can interpolate.
 */
export interface LeaveTypeTone {
  fill: string;
  border: string;
}

const TONES: LeaveTypeTone[] = [
  { fill: "#bae6fd", border: "#0284c7" }, // sky
  { fill: "#a7f3d0", border: "#059669" }, // emerald
  { fill: "#ddd6fe", border: "#7c3aed" }, // violet
  { fill: "#fecdd3", border: "#e11d48" }, // rose
  { fill: "#a5f3fc", border: "#0891b2" }, // cyan
  { fill: "#fde68a", border: "#d97706" }, // amber
];

function keyFor(leaveType: CalendarLeaveTypeRef): string {
  return leaveType.code || leaveType.name || String(leaveType.id ?? "");
}

export function leaveTypeTone(leaveType: CalendarLeaveTypeRef): LeaveTypeTone {
  const key = keyFor(leaveType);
  const hash = Array.from(key).reduce(
    (acc, char) => acc + char.charCodeAt(0),
    0
  );
  return TONES[hash % TONES.length];
}
