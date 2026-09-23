"use client";

import { useCallback, useEffect, useRef } from "react";

/**
 * Guard against losing unsaved edits: warns on browser unload and provides
 * ``confirmLeave`` for in-app navigation performed by the caller.
 */
export function useUnsavedChangesGuard(dirty: boolean) {
  const dirtyRef = useRef(dirty);

  useEffect(() => {
    dirtyRef.current = dirty;
  }, [dirty]);

  useEffect(() => {
    if (!dirty) return;

    function beforeUnload(event: BeforeUnloadEvent) {
      event.preventDefault();
      event.returnValue = "";
    }

    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [dirty]);

  const confirmLeave = useCallback((): boolean => {
    if (!dirtyRef.current) return true;
    return window.confirm(
      "You have unsaved changes that will be lost. Continue?"
    );
  }, []);

  return { confirmLeave };
}