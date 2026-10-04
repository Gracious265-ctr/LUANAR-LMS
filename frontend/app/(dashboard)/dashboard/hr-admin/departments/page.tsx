import { redirect } from "next/navigation";

import { DepartmentsSection } from "@/components/hr/DepartmentsSection";
import { getCurrentUser } from "@/lib/auth";
import { listDepartments } from "@/lib/departments";
import { FadeIn } from "@/components/motion/FadeIn";

export default async function DepartmentsPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  if (user.role !== "hr") redirect("/dashboard");

  // Retired rows stay listed: retiring keeps the department's history readable,
  // and hiding the row would hide the applications that still name it.
  const departments = await listDepartments(true);

  return (
    <FadeIn>
      <div className="space-y-6">
        <h2 className="text-2xl font-bold text-text-primary">Departments</h2>
        <DepartmentsSection departments={departments} />
      </div>
    </FadeIn>
  );
}
