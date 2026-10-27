"use client";

import { Stepper, type Step } from "@/components/ui/Stepper";

/** One stage of a multi-page form: the name on the rail and its position. */
export interface FormProgressStage {
  id: string;
  label: string;
}

/**
 * The rail above a form that is split across pages.
 *
 * The stages are the form's own pages, in order, and only the current one is
 * marked `current`: everything before it is done, everything after it is still
 * pending. Nothing here is interactive — moving between pages stays the form's
 * decision, so the rail cannot be used to skip a page that has not validated.
 *
 * Reuses `Stepper` so a form's progress reads like every other sequence in the
 * app (the leave-type form already does this), compact and without avatars
 * because a stage is a page, not a person.
 */
export function FormProgress({
  stages,
  current,
}: {
  stages: FormProgressStage[];
  current: string;
}) {
  const currentIndex = stages.findIndex((stage) => stage.id === current);

  const steps: Step[] = stages.map((stage, index) => ({
    id: stage.id,
    label: stage.label,
    status:
      currentIndex === -1 || index > currentIndex
        ? "pending"
        : index === currentIndex
          ? "current"
          : "completed",
  }));

  return (
    <div
      role="group"
      aria-label="Form progress"
      className="border-b border-border-default pb-4"
    >
      <Stepper
        steps={steps}
        orientation="horizontal"
        size="sm"
        showAvatars={false}
      />
    </div>
  );
}
