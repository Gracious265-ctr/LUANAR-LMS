import { redirect } from "next/navigation";

import { PlanSettingsForm } from "@/components/plans/plan-settings-form";
import { PlansAdminTable } from "@/components/plans/plans-admin-table";
import { getCurrentUser } from "@/lib/auth";
import { FadeIn } from "@/components/motion/FadeIn";

const HR_ROLE = "hr";

/**
 * HR's oversight of leave day plans: every plan in the institution, and the
 * one setting that governs the confirmation window.
 *
 * Guarded here as well as in the sidebar: the nav item is hidden for
 * non-HR callers, but that is presentation. The API answers 403 regardless,
 * and this page refuses to render the frame at all.
 */
export default async function HRPlansPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== HR_ROLE) {
    redirect("/dashboard");
  }

  return (
    <FadeIn>
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-text-primary">
            Leave Day Plans
          </h2>
          <p className="text-sm text-text-secondary">
            Every plan in the institution, and how long an owner has to confirm a
            reserved block before it is released.
          </p>
        </div>

        <section className="space-y-3">
          <h3 className="text-lg font-semibold text-text-primary">All plans</h3>
          <PlansAdminTable />
        </section>

        <section className="space-y-3">
          <h3 className="text-lg font-semibold text-text-primary">Settings</h3>
          <PlanSettingsForm />
        </section>
      </div>
    </FadeIn>
  );
}
