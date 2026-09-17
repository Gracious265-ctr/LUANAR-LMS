"use client";

import { useCallback, useEffect, useState } from "react";

import {
  type LeaveApplication,
  getLeaveApplications,
} from "@/lib/leave-api";

export function useLeaveApplications(statusFilter?: string) {
  const [applications, setApplications] = useState<LeaveApplication[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchApplications = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getLeaveApplications();
      let results = data.results;
      if (statusFilter) {
        results = results.filter((app) => app.status === statusFilter);
      }
      setApplications(results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load applications");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchApplications();
  }, [fetchApplications]);

  return { applications, loading, error, refetch: fetchApplications };
}
