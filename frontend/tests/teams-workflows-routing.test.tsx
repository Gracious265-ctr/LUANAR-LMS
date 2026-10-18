import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import TeamWorkflowsPage from "@/app/(dashboard)/organisation/teams/[id]/workflows/page";
import WorkflowDetailPage from "@/app/(dashboard)/organisation/teams/[id]/workflows/[workflowId]/page";
import { getCurrentUser } from "@/lib/auth";
import { getTeam, listTeamWorkflows } from "@/lib/teams";
import { getWorkflow, workflowStateLabel } from "@/lib/workflows";

vi.mock("next/navigation", () => ({ redirect: vi.fn(), notFound: vi.fn() }));
vi.mock("@/lib/auth", () => ({ getCurrentUser: vi.fn() }));
vi.mock("@/lib/teams", () => ({
  getTeam: vi.fn(),
  listTeamWorkflows: vi.fn(),
}));
vi.mock("@/lib/workflows", () => ({
  getWorkflow: vi.fn(),
  workflowStateLabel: vi.fn((state: string) => state),
}));
// The controls fetch and write on click; their own tests cover them, so render
// a placeholder here and assert only who the page offers them to.
vi.mock("@/components/hr/workflow-routing-actions", () => ({
  WorkflowRoutingActions: () => <div data-testid="routing-actions" />,
}));

const team = {
  id: 1,
  name: "Registry team",
  code: "registry-team",
  description: "",
  category: "administration",
  campus: null,
  campus_name: "",
  workflow: 5,
  workflow_name: "Registry approval",
  workflows: [],
  status: "active",
  effective_from: null,
  effective_to: null,
  is_effective: true,
  stage_roles: [],
  member_count: 0,
  members: [],
  sections: [],
  created_at: "",
  updated_at: "",
};

const workflow = {
  id: 5,
  name: "Registry approval",
  team: 1,
  team_name: "Registry team",
  effective_from: null,
  is_active: true,
  state: "routing",
  is_routing: true,
  section_count: 1,
  sections: [],
  members: [],
};

function asHr() {
  vi.mocked(getCurrentUser).mockResolvedValue({
    id: 1,
    email: "hr@luanar",
    role: "hr",
    full_name: "Hilda HR",
  });
}

function asManager() {
  vi.mocked(getCurrentUser).mockResolvedValue({
    id: 2,
    email: "manager@luanar",
    role: "employee",
    full_name: "Moses Manager",
    manages_teams: true,
  });
}

async function renderListPage() {
  render(
    await TeamWorkflowsPage({ params: Promise.resolve({ id: "1" }) })
  );
}

async function renderDetailPage() {
  render(
    await WorkflowDetailPage({
      params: Promise.resolve({ id: "1", workflowId: "5" }),
    })
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getTeam).mockResolvedValue(team as never);
  vi.mocked(listTeamWorkflows).mockResolvedValue([
    {
      id: 5,
      name: "Registry approval",
      is_routing: true,
      section_count: 1,
      effective_from: null,
      is_active: true,
    },
  ]);
  vi.mocked(getWorkflow).mockResolvedValue(workflow as never);
  vi.mocked(workflowStateLabel).mockReturnValue("In force");
});

describe("workflow routing is the manager's call", () => {
  it("offers the manager the routing controls on the workflows list", async () => {
    asManager();
    await renderListPage();

    expect(screen.getByTestId("routing-actions")).toBeInTheDocument();
    expect(screen.queryByText(/manager's call/)).not.toBeInTheDocument();
  });

  it("tells HR to ask the manager on the workflows list", async () => {
    asHr();
    await renderListPage();

    expect(screen.queryByTestId("routing-actions")).not.toBeInTheDocument();
    expect(screen.getByText(/manager's call/)).toBeInTheDocument();
  });

  it("offers the manager the routing controls on a workflow's own page", async () => {
    asManager();
    await renderDetailPage();

    expect(screen.getByTestId("routing-actions")).toBeInTheDocument();
    expect(screen.queryByText(/manager's call/)).not.toBeInTheDocument();
  });

  it("tells HR to ask the manager on a workflow's own page", async () => {
    asHr();
    await renderDetailPage();

    expect(screen.queryByTestId("routing-actions")).not.toBeInTheDocument();
    expect(screen.getByText(/manager's call/)).toBeInTheDocument();
  });
});
