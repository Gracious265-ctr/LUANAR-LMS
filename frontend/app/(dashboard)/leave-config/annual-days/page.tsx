import { AnnualDaysConfig } from "@/components/hr/annual-days-config";
import { FadeIn } from "@/components/motion/FadeIn";
import { requireLeaveConfigAccess } from "@/lib/leave-config-server";

export const metadata = {
  title: "Annual Days",
};

/**
 * Annual-days configuration inside Leave Configuration (spec 3.5 extension).
 *
 * Annual days are grade-based — a band, a leave type and a financial year —
 * so this page is the Leave Configuration home for the same `/entitlements/`
 * registry the HR-admin page exposes. `?grade=` answers "what does this grade
 * get"; the table below it is where HR creates and edits the bands.
 */
export default async function AnnualDaysPage({
  searchParams,
}: {
  searchParams: Promise<{ grade?: string | string[] }>;
}) {
  await requireLeaveConfigAccess();

  const { grade } = await searchParams;
  const queryGrade = typeof grade === "string" ? grade.trim() : "";

  return (
    <FadeIn>
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-text-primary">
            Annual days
          </h2>
          <p className="text-text-secondary">
            Grant annual leave days by grade band, leave type and financial year.
          </p>
        </div>

        <AnnualDaysConfig
          grade={queryGrade}
          basePath="/leave-config/annual-days"
        />
      </div>
    </FadeIn>
  );
}
