import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

const APP_TIME_ZONE = process.env.NEXT_PUBLIC_APP_TIME_ZONE || "Africa/Blantyre";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function currentDateIso(date: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: APP_TIME_ZONE,
  }).format(date);
}

export function apiErrorMessage(data: unknown): string {
  if (typeof data === "string") {
    return data;
  }
  if (data && typeof data === "object") {
    const obj = data as Record<string, unknown>;
    if (typeof obj.detail === "string") {
      return obj.detail;
    }
    const parts: string[] = [];
    for (const [field, value] of Object.entries(obj)) {
      if (Array.isArray(value) && typeof value[0] === "string") {
        parts.push(`${field}: ${value[0]}`);
      } else if (typeof value === "string") {
        parts.push(`${field}: ${value}`);
      }
    }
    if (parts.length > 0) {
      return parts.join(", ");
    }
  }
  return "An error occurred. Please try again.";
}
