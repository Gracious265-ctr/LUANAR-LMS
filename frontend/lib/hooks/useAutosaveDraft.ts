"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { updateLeaveApplication, type LeaveApplication } from "@/lib/leave-api";

type SaveStatus = "idle" | "saving" | "saved" | "error";

export function useAutosaveDraft(
  applicationId: string | null,
  data: Record<string, unknown>,
  delay = 800,
  onSaved?: (application: LeaveApplication) => void
) {
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSavedRef = useRef<string>("");
  const isInitialRef = useRef(true);
  const startedWithIdRef = useRef(Boolean(applicationId));
  const onSavedRef = useRef(onSaved);

  useEffect(() => {
    onSavedRef.current = onSaved;
  }, [onSaved]);

  const save = useCallback(
    async (patchData: Record<string, unknown>) => {
      if (!applicationId) return;
      try {
        setSaveStatus("saving");
        const saved = await updateLeaveApplication(applicationId, patchData);
        onSavedRef.current?.(saved);
        setSaveStatus("saved");
      } catch {
        setSaveStatus("error");
      }
    },
    [applicationId]
  );

  useEffect(() => {
    if (!applicationId) return;

    const serialized = JSON.stringify(data);
    if (serialized === lastSavedRef.current) return;
    if (isInitialRef.current && startedWithIdRef.current) {
      isInitialRef.current = false;
      lastSavedRef.current = serialized;
      return;
    }
    isInitialRef.current = false;

    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }

    timerRef.current = setTimeout(() => {
      save(data);
      lastSavedRef.current = JSON.stringify(data);
    }, delay);

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [applicationId, data, delay, save]);

  const resetSaveStatus = useCallback(() => {
    setSaveStatus("idle");
  }, []);

  return { saveStatus, resetSaveStatus };
}
