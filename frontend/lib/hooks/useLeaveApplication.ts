"use client";

import { useCallback, useEffect, useState } from "react";

import {
  type LeaveApplication,
  getLeaveApplication,
} from "@/lib/leave-api";

export function useLeaveApplication(id: string | null) {
  const [application, setApplication] = useState<LeaveApplication | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchApplication = useCallback(async () => {
    if (!id) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const data = await getLeaveApplication(id);
      setApplication(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load application");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchApplication();
  }, [fetchApplication]);

  return { application, loading, error, refetch: fetchApplication, setApplication };
}
