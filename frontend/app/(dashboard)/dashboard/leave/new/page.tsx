import { LeaveApplicationForm } from "@/components/leave/LeaveApplicationForm";

export default async function NewLeavePage() {
  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-6">
        <h2 className="text-xl font-semibold tracking-tight text-text-primary">
          New Leave Application
        </h2>
        <p className="text-text-secondary text-sm">
          Fill in the details below to start your leave application.
        </p>
      </div>
      <LeaveApplicationForm mode="create" />
    </div>
  );
}