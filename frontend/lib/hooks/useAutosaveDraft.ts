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
  const pendingRef = useRef(false);
  const latestDataRef = useRef(data);
  const startedWithIdRef = useRef(Boolean(applicationId));
  const onSavedRef = useRef(onSaved);

  useEffect(() => {
    onSavedRef.current = onSaved;
  }, [onSaved]);

  useEffect(() => {
    latestDataRef.current = data;
  }, [data]);

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

    pendingRef.current = true;
    latestDataRef.current = data;

    timerRef.current = setTimeout(() => {
      pendingRef.current = false;
      lastSavedRef.current = JSON.stringify(latestDataRef.current);
      void save(latestDataRef.current);
    }, delay);

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [applicationId, data, delay, save]);

  /**
   * Persist any debounced change immediately.
   *
   * The effect cleanup above only clears the pending timer, so a save scheduled
   * in the last `delay` ms is dropped when the component unmounts. A full-page
   * form made that easy to miss; the compose overlay unmounts on close, so the
   * last keystrokes are lost unless the caller flushes first.
   */
  const flush = useCallback(() => {
    if (!pendingRef.current) return;
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    pendingRef.current = false;
    lastSavedRef.current = JSON.stringify(latestDataRef.current);
    void save(latestDataRef.current);
  }, [save]);

  const resetSaveStatus = useCallback(() => {
    setSaveStatus("idle");
  }, []);

  return { saveStatus, resetSaveStatus, flush };
}
