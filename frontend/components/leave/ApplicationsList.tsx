"use client";

import { FileText, Plus } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useLeaveApplications } from "@/lib/hooks/useLeaveApplications";
import { getLeaveTypes } from "@/lib/services/leaveTypes";
import { Button } from "@/components/ui/button";
import { ApplicationCard } from "./ApplicationCard";
import { Card } from "@/components/ui/card";

export function ApplicationsList() {
  const { applications, loading, error, refetch } = useLeaveApplications();
  const [leaveTypeNames, setLeaveTypeNames] = useState<Record<number, string>>({});

  useEffect(() => {
    getLeaveTypes().then((types) => {
      const map: Record<number, string> = {};
      for (const t of types) {
        map[t.id] = t.name;
      }
      setLeaveTypeNames(map);
    });
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-32 animate-pulse rounded-xl bg-surface-muted" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <Card className="text-center">
        <p className="text-status-rejected text-sm">{error}</p>
        <Button onClick={refetch} variant="link" size="sm" className="mt-2 h-auto text-text-link">
          Try again
        </Button>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-text-primary">My Applications</h2>
          <p className="text-text-secondary text-sm">
            {applications.length} application{applications.length === 1 ? "" : "s"}
          </p>
        </div>
        <Link
          href="/dashboard/leave/new"
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-button-primary text-button-primary-foreground font-medium text-sm hover:bg-button-primary-hover transition-colors"
        >
          <Plus className="h-4 w-4" />
          New Application
        </Link>
      </div>

      {applications.length === 0 ? (
        <Card className="text-center">
          <FileText className="h-12 w-12 mx-auto text-text-disabled mb-4" />
          <h3 className="text-lg font-semibold text-text-primary mb-2">
            No applications yet
          </h3>
          <p className="text-text-secondary text-sm mb-4">
            Start a new leave application to see it here.
          </p>
          <Link
            href="/dashboard/leave/new"
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-button-primary text-button-primary-foreground font-medium text-sm hover:bg-button-primary-hover transition-colors"
          >
            <Plus className="h-4 w-4" />
            New Application
          </Link>
        </Card>
      ) : (
        <div className="grid gap-4">
          {applications.map((app) => (
            <ApplicationCard
              key={app.id}
              application={app}
              leaveTypeName={
                app.leave_type_id != null
                  ? leaveTypeNames[app.leave_type_id] || `Type #${app.leave_type_id}`
                  : "Not selected"
              }
              onDelete={refetch}
            />
          ))}
        </div>
      )}
    </div>
  );
}