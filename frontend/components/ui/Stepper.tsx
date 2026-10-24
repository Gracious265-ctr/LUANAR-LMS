"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import { Check, Clock } from "lucide-react";

import { cn } from "@/lib/utils";

export type StepStatus =
  | "completed"
  | "current"
  | "pending"
  | "skipped"
  | "blocked"
  | "error";

export interface Step {
  id: string;
  label: string;
  sublabel?: string;
  status: StepStatus;
  actor?: { id: string; name: string } | null;
  timestamp?: string | null;
  isActing?: boolean;
  detail?: string | null;
}

interface StepperProps {
  steps: Step[];
  orientation?: "horizontal" | "vertical" | "auto";
  compact?: boolean;
  className?: string;
  activeStep?: number;
  onStepChange?: (index: number) => void;
  interactive?: boolean;
}

export function Stepper({
  steps,
  className,
  activeStep: controlledActiveStep,
  onStepChange,
  interactive = false,
}: StepperProps) {
  const prefersReducedMotion = useReducedMotion();
  const [internalActiveStep, setInternalActiveStep] = useState(0);

  useEffect(() => {
    if (controlledActiveStep !== undefined) {
      return;
    }
    if (interactive) {
      const currentIndex = steps.findIndex((s) => s.status === "current");
      if (currentIndex >= 0) {
        setInternalActiveStep(currentIndex);
      } else {
        const lastCompleted = steps
          .map((s, i) => ({ s, i }))
          .filter((x) => x.s.status === "completed")
          .pop();
        if (lastCompleted) {
          setInternalActiveStep(lastCompleted.i);
        }
      }
    }
  }, [steps, controlledActiveStep, interactive]);

  const activeStep =
    controlledActiveStep !== undefined ? controlledActiveStep : internalActiveStep;

  const setActiveStep = (index: number) => {
    if (!interactive) return;
    if (controlledActiveStep === undefined) {
      setInternalActiveStep(index);
    }
    onStepChange?.(index);
  };

  const progress = steps.length > 1 ? activeStep / (steps.length - 1) : 1;

  return (
    <div className={cn("mx-auto w-full max-w-3xl", className)}>
      <div className="relative">
        <div
          className="absolute top-5 h-0.5 bg-border"
          style={{ left: "12.5%", right: "12.5%" }}
        />
        <motion.div
          className="absolute top-5 h-0.5 bg-primary origin-left"
          style={{ left: "12.5%", right: "12.5%" }}
          initial={false}
          animate={{ scaleX: progress }}
          transition={{ type: "spring", stiffness: 120, damping: 20 }}
        />
        <motion.span
          className="absolute size-2 rounded-full bg-primary"
          style={{ top: 21, x: "-50%", y: "-50%" }}
          initial={{ left: "12.5%" }}
          animate={{ left: `${12.5 + progress * 75}%` }}
          transition={{ type: "spring", stiffness: 160, damping: 24 }}
        />
        <div className="relative flex items-start justify-between">
          {steps.map((step, index) => {
            const isActive = index === activeStep;
            const isCompleted =
              step.status === "completed" || index < activeStep;
            return (
              <div
                key={step.id}
                className="flex flex-1 flex-col items-center gap-2"
              >
                <button
                  type="button"
                  onClick={() => setActiveStep(index)}
                  disabled={!interactive}
                  aria-current={isActive ? "step" : undefined}
                  aria-label={`${step.label} step`}
                  className={cn(
                    "group relative z-10 flex size-10 cursor-pointer items-center justify-center rounded-full transition-colors duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                    !interactive && "cursor-default"
                  )}
                >
                  <span
                    className={cn(
                      "absolute inset-0 rounded-full transition-colors duration-300",
                      isCompleted || isActive
                        ? "bg-primary"
                        : "bg-muted group-hover:bg-muted/80"
                    )}
                  />
                  {isActive && !prefersReducedMotion && (
                    <motion.span
                      className="absolute inset-0 rounded-full ring-2 ring-primary/50"
                      initial={{ scale: 1, opacity: 1 }}
                      animate={{
                        scale: [1, 1.45, 1],
                        opacity: [1, 0.2, 1],
                      }}
                      transition={{
                        duration: 2.2,
                        repeat: Infinity,
                        repeatType: "mirror",
                        ease: "easeInOut",
                      }}
                    />
                  )}
                  <motion.div
                    className="relative flex items-center justify-center"
                    animate={{ scale: isActive ? 1.1 : 1 }}
                    transition={{
                      type: "spring",
                      stiffness: 320,
                      damping: 18,
                    }}
                  >
                    <AnimatePresence mode="wait" initial={false}>
                      {isCompleted ? (
                        <motion.span
                          key="check"
                          initial={{ scale: 0, rotate: -90, opacity: 0 }}
                          animate={{ scale: 1, rotate: 0, opacity: 1 }}
                          exit={{ scale: 0, rotate: 90, opacity: 0 }}
                          transition={{
                            type: "spring",
                            stiffness: 400,
                            damping: 22,
                          }}
                          className="flex items-center justify-center text-teal-400"
                        >
                          <Check className="size-5" strokeWidth={3} />
                        </motion.span>
                      ) : (
                        <motion.span
                          key="icon"
                          initial={{ scale: 0, opacity: 0 }}
                          animate={{ scale: 1, opacity: 1 }}
                          exit={{ scale: 0, opacity: 0 }}
                          transition={{
                            type: "spring",
                            stiffness: 400,
                            damping: 22,
                          }}
                          className="flex items-center justify-center"
                        >
                          <Clock
                            className={cn(
                              "size-5",
                              isActive
                                ? "text-primary-foreground"
                                : "text-muted-foreground"
                            )}
                          />
                        </motion.span>
                      )}
                    </AnimatePresence>
                  </motion.div>
                </button>
                <span
                  className={cn(
                    "text-xs font-medium transition-colors duration-300",
                    isActive || isCompleted
                      ? "text-foreground"
                      : "text-muted-foreground"
                  )}
                >
                  {step.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
