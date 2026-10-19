"use client";

import { useRouter } from "next/navigation";
import { CalendarPlus } from "lucide-react";

import { MyPlans } from "@/components/plans/MyPlans";
import { Button } from "@/components/ui/button";

/** My Plans — the Leave Plans module's landing page (spec 3.4). */
export default function PlansPage() {
  const router = useRouter();

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text-primary">
            Leave Plans
          </h1>
          <p className="text-text-muted">
            Plan your leave ahead of time — nothing here is submitted until you apply.
          </p>
        </div>
        <Button
          variant="primary"
          onClick={() => router.push("/dashboard/plans/new")}
        >
          <CalendarPlus className="h-4 w-4" aria-hidden="true" />
          Create a Plan
        </Button>
      </div>

      <MyPlans />
    </div>
  );
}
