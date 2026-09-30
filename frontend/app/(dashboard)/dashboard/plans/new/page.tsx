import { PlanForm } from "@/components/plans/plan-form";

export default async function NewPlanPage() {
  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6">
        <h2 className="text-xl font-semibold tracking-tight text-text-primary">
          New leave day plan
        </h2>
        <p className="text-sm text-text-secondary">
          A plan groups the leave you intend to take into one approval, then
          reserves each block once it is approved.
        </p>
      </div>
      <PlanForm />
    </div>
  );
}
