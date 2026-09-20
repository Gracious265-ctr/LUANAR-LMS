"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { updateLeaveApplication } from "@/lib/leave-api";

type SaveStatus = "idle" | "saving" | "saved" | "error";

export function useAutosaveDraft(
  applicationId: string | null,
  data: Record<string, unknown>,
  delay = 800
) {
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSavedRef = useRef<string>("");
  const isInitialRef = useRef(true);

  const save = useCallback(
    async (patchData: Record<string, unknown>) => {
      if (!applicationId) return;
      try {
        setSaveStatus("saving");
        await updateLeaveApplication(applicationId, patchData);
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
    if (isInitialRef.current) {
      isInitialRef.current = false;
      lastSavedRef.current = serialized;
      return;
    }

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
