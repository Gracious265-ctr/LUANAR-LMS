import { redirect } from "next/navigation";

import { AnnualDaysConfig } from "@/components/hr/annual-days-config";
import { getCurrentUser } from "@/lib/auth";
import { FadeIn } from "@/components/motion/FadeIn";

export default async function EntitlementsPage({
  searchParams,
}: {
  searchParams: Promise<{ grade?: string | string[] }>;
}) {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  const { grade } = await searchParams;
  const queryGrade = typeof grade === "string" ? grade.trim() : "";

  return (
    <FadeIn>
      <div className="space-y-6">
        <div>
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-text-primary">Entitlements</h2>
            <p className="text-text-secondary">Configure grade ranges and annual leave entitlements.</p>
          </div>
        </div>

        <AnnualDaysConfig grade={queryGrade} />
      </div>
    </FadeIn>
  );
}
