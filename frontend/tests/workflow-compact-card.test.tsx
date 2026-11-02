import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { WorkflowCompactCard } from "@/components/hr/workflow-compact-card";
import type { WorkflowRef } from "@/lib/teams";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

const workflow: WorkflowRef = {
  id: 12,
  name: "Academic approval",
  is_routing: true,
  section_count: 3,
  effective_from: null,
  is_active: true,
};

describe("WorkflowCompactCard", () => {
  it("links every chain to its member roster", () => {
    render(<WorkflowCompactCard workflow={workflow} teamId={4} />);

    expect(screen.getByRole("link", { name: "View members" })).toHaveAttribute(
      "href",
      "/dashboard/teams/4/workflows/12#members"
    );
  });

  it("still lets a non-manager view the members, without offering Edit", () => {
    render(
      <WorkflowCompactCard
        workflow={workflow}
        teamId={4}
        canMakeDefault={false}
      />
    );

    expect(screen.getByRole("link", { name: "View members" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Edit" })).not.toBeInTheDocument();
  });
});
