import { apiClient } from "./api-client";

export type EmployeeCategory = "academic" | "administration";

export interface Employee {
  id: number;
  user_id: number;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: string;
  designation: string;
  department: string;
  category: EmployeeCategory;
  grade: string;
  appointment_date: string | null;
  is_active: boolean;
}

export interface EmployeeInput {
  email: string;
  first_name: string;
  last_name: string;
  designation?: string;
  department?: string;
  category?: EmployeeCategory;
  grade?: string;
  appointment_date?: string | null;
  is_active?: boolean;
}

export interface EmployeeListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Employee[];
}

export async function listEmployees(search = ""): Promise<EmployeeListResponse> {
  const query = search ? `?search=${encodeURIComponent(search)}` : "";
  return apiClient<EmployeeListResponse>(`/api/v1/employees/${query}`);
}

export async function getEmployee(id: number | string): Promise<Employee> {
  return apiClient<Employee>(`/api/v1/employees/${id}/`);
}