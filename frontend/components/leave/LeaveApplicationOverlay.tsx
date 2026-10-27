"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import {
  LeaveApplicationForm,
  type LeaveApplicationFormHandle,
} from "@/components/leave/LeaveApplicationForm";
import { LeaveReviewPanel } from "@/components/leave/LeaveReviewPanel";
import { LeaveSubmissionResult } from "@/components/leave/LeaveSubmissionResult";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export type LeaveOverlayStage = "form" | "review" | "done";

export interface LeaveApplicationOverlayProps {
  open: boolean;
  /** `edit` targets an existing draft; `create` starts a new application. */
  mode: "create" | "edit";
  applicationId?: string;
  /** Initial stage, so a `/review` or `/submitted` link can deep-link into it. */
  initialStage?: LeaveOverlayStage;
  /**
   * The list route that hosts this overlay, used when a freshly created draft
   * learns its id and the URL has to name it. Defaults to the drafts list.
   */
  basePath?: string;
  onOpenChange: (open: boolean) => void;
  /** Called after a successful submit so the list can refetch. */
  onSubmitted?: (applicationId: string) => void;
  /**
   * Reports a stage transition so the host can put it in the URL.
   *
   * The host must use `replace` for this, not `push`: opening the overlay
   * already added one history entry, and `close()` steps back exactly once. A
   * push per stage would leave the user in the overlay after closing it, one
   * Back press per stage visited.
   *
   * `applicationId` is passed because a create flow learns its draft id partway
   * through, and the URL has to name the draft from then on.
   */
  onStageChange?: (stage: LeaveOverlayStage, applicationId?: string) => void;
}

const TITLES: Record<LeaveOverlayStage, { title: string; description: string }> = {
  form: {
    title: "New leave application",
    description:
      "Fill in the details below. Your progress is saved as a draft as you type.",
  },
  review: {
    title: "Review your application",
    description: "Check the details below before submitting.",
  },
  done: {
    title: "Application submitted",
    description: "Keep this reference number to track your application.",
  },
};

/**
 * Applies for leave without leaving the page.
 *
 * The whole three-step journey lives here: details, review, then confirmation.
 * Stage is lifted to the URL by the host so the overlay survives a refresh and
 * the browser Back button steps out of it.
 *
 * Closing mid-form is not destructive — autosave has already persisted the
 * draft — but the pending debounced save is flushed first so the last few
 * keystrokes are not lost.
 */
export function LeaveApplicationOverlay(props: LeaveApplicationOverlayProps) {
  const { open, mode, applicationId, initialStage = "form" } = props;
  const stage: LeaveOverlayStage = initialStage;

  if (!open) return null;

  // Remounting on the target identity is what resets stage and form state when
  // the user moves from one application to another. Deriving it here keeps the
  // reset out of an effect.
  return (
    <LeaveApplicationOverlayInner
      key={`${mode}:${applicationId ?? "new"}:${stage}`}
      {...props}
    />
  );
}

function LeaveApplicationOverlayInner({
  mode,
  applicationId,
  initialStage,
  basePath = "/dashboard/leave/drafts",
  onOpenChange,
  onSubmitted,
  onStageChange,
}: LeaveApplicationOverlayProps) {
  const router = useRouter();
  const [stage, setStage] = useState<LeaveOverlayStage>(initialStage ?? "form");
  const [draftId, setDraftId] = useState<string | null>(
    mode === "edit" ? (applicationId ?? null) : null
  );
  // Deep-linking to `?edit=<id>&stage=done` lands here without a submit in this
  // session, so seed the confirmation from the target application.
  const [submittedId, setSubmittedId] = useState<string | null>(
    initialStage === "done" ? (applicationId ?? null) : null

  );
  const formRef = useRef<LeaveApplicationFormHandle | null>(null);

  const handleOpenChange = (next: boolean) => {
    if (!next) {
      formRef.current?.flush();
    }
    onOpenChange(next);
  };

  /**
   * Moves to a stage and reports it so the host can mirror it into the URL.
   * The local `setStage` and the host's rewrite agree, so the stage stays
   * correct whether or not the host acts on the report.
   */
  const goToStage = (
    next: LeaveOverlayStage,
    id: string | null
  ) => {
    setStage(next);
    onStageChange?.(next, id ?? undefined);
  };

  const handleDraftCreated = (id: string) => {
    setDraftId(id);
    // `replace`, not `push`: the user opened the overlay deliberately, so a
    // refresh should resume this draft rather than re-trigger the Back button.
    router.replace(`${basePath}?edit=${id}`);
  };

  const handleSubmitted = (id: string) => {
    setSubmittedId(id);
    goToStage("done", id);
    onSubmitted?.(id);
  };

  const heading = TITLES[stage];

  return (
    <Dialog open onOpenChange={handleOpenChange}>
      <DialogContent
        showCloseButton={stage !== "done"}
        className="max-w-2xl"
        scrollable
        onEscapeKeyDown={() => {
          if (stage !== "done") formRef.current?.flush();
        }}
      >
        <DialogHeader>
          <DialogTitle>{heading.title}</DialogTitle>
          <DialogDescription>{heading.description}</DialogDescription>
        </DialogHeader>

        {stage === "form" && (
          <LeaveApplicationForm
            ref={formRef}
            mode={mode}
            applicationId={applicationId}
            onDraftCreated={handleDraftCreated}
            onContinueToReview={(id) => {
              setDraftId(id);
              goToStage("review", id);
            }}
          />
        )}

        {stage === "review" && draftId && (
          <LeaveReviewPanel
            applicationId={draftId}
            onSubmitted={handleSubmitted}
            onEdit={() => goToStage("form", draftId)}
            showBackLink={false}
          />
        )}

        {stage === "done" && submittedId && (
          <LeaveSubmissionResult
            applicationId={submittedId}
            onDone={() => handleOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
