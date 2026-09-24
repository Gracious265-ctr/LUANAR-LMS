"use client";

import { useState } from "react";

import { CancellationRequestsTable } from "../cancellation/CancellationRequestsTable";
import { Tabs } from "../ui/tabs";
import { ApprovalsList } from "./approvals-list";

type Section = "applications" | "cancellations";

/**
 * Top-level switch for the approvals area: the Unit 16 applications queue
 * (unchanged) against the Unit 18 cancellation requests queue.
 */
export function ApprovalsHub() {
  const [section, setSection] = useState<Section>("applications");

  return (
    <div className="space-y-6">
      <header className="space-y-4">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Approvals</h1>
          <p className="text-sm text-text-secondary">
            {section === "applications"
              ? "Applications waiting for your decision."
              : "Leave cancellation requests waiting for your decision."}
          </p>
        </div>
        <Tabs
          label="Approvals sections"
          tabs={[
            { value: "applications", label: "Applications" },
            { value: "cancellations", label: "Cancellation requests" },
          ]}
          value={section}
          onChange={setSection}
        />
      </header>

      {section === "applications" ? (
        <ApprovalsList />
      ) : (
        <CancellationRequestsTable />
      )}
    </div>
  );
}