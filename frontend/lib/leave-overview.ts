import { apiClient } from "./api-client";

export interface EmployeeProfileInfo {
  grade: string;
  department: string;
  designation: string;
  category: string;
  gender: string;
  appointment_date: string;
}

export interface FinancialYearInfo {
  label: string;
  start: string;
  end: string;
}

export interface LeaveOverview {
  profile: EmployeeProfileInfo | null;
  entitlement: number | null;
  used: number | null;
  available: number | null;
  financial_year: FinancialYearInfo | null;
  pending_applications: number;
  upcoming_leaves: number;
  next_leave_start: string | null;
}

export async function getLeaveOverview(): Promise<LeaveOverview> {
  return apiClient<LeaveOverview>("/api/v1/leave/my/overview/");
}

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

export function formatIsoDate(iso: string): string {
  const [year, month, day] = iso.split("-");
  const parsedMonth = Number(month);
  if (
    year.length !== 4 ||
    Number.isNaN(parsedMonth) ||
    parsedMonth < 1 ||
    parsedMonth > 12 ||
    day.length !== 2
  ) {
    return iso;
  }
  return `${day} ${MONTHS[parsedMonth - 1]} ${year}`;
}