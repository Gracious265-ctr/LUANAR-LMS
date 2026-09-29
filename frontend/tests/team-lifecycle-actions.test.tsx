import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TeamLifecycleActions } from "@/components/hr/team-lifecycle-actions";
import { makeTeam } from "@/lib/teams/__fixtures__";
import type { TeamReadiness } from "@/lib/teams";
import { activateTeam, deactivateTeam, validateTeam } from "@/lib/teams-client";

const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh }),
}));

vi.mock("@/lib/teams-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/teams-client")>();
  return {
    ...actual,
    activateTeam: vi.fn(),
    deactivateTeam: vi.fn(),
    validateTeam: vi.fn(),
  };
});

const notReady: TeamReadiness = {
  team: "Bunda College Faculty",
  status: "draft",
  ready: false,
  issues: [
    {
      code: "no_approver",
      field: "sections",
      message:
        'Nobody can act on the "Department head" step (Head of Department). Add at least one active member, or a holder of the role.',
      section: 2,
      approver_role: "hod",
    },
    {
      code: "no_sections",
      field: "workflow",
      message: "This team has no approval chain, so nothing can be approved.",
      section: null,
      approver_role: null,
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("TeamLifecycleActions", () => {
  it("lists every reason a team cannot be put into force, in one pass", async () => {
    vi.mocked(validateTeam).mockResolvedValue(notReady);
    render(<TeamLifecycleActions team={makeTeam()} />);

    fireEvent.click(screen.getByRole("button", { name: "Check readiness" }));

    expect(
      await screen.findByText(/Bunda College Faculty cannot be put into force yet/)
    ).toBeInTheDocument();
    expect(screen.getByText(/Nobody can act on the "Department head" step/)).toBeInTheDocument();
    expect(
      screen.getByText("This team has no approval chain, so nothing can be approved.")
    ).toBeInTheDocument();
    expect(screen.getByText(/Fix 2 problems/)).toBeInTheDocument();
  });

  it("says so plainly when a team is ready", async () => {
    vi.mocked(validateTeam).mockResolvedValue({
      team: "Bunda College Faculty",
      status: "draft",
      ready: true,
      issues: [],
    });
    render(<TeamLifecycleActions team={makeTeam()} />);

    fireEvent.click(screen.getByRole("button", { name: "Check readiness" }));

    expect(
      await screen.findByText(/Bunda College Faculty is ready to put into force/)
    ).toBeInTheDocument();
  });

  it("shows the reasons a refused activation gave, rather than a bare failure", async () => {
    // The backend refuses an unready activation with the same issue list the
    // readiness check returns, so the two cannot disagree about why.
    vi.mocked(activateTeam).mockRejectedValue(
      Object.assign(new Error(notReady.issues[0].message), {
        readiness: notReady,
      })
    );
    render(<TeamLifecycleActions team={makeTeam()} />);

    fireEvent.click(screen.getByRole("button", { name: "Put into force" }));

    expect(
      await screen.findByText(/Bunda College Faculty cannot be put into force yet/)
    ).toBeInTheDocument();
    expect(refresh).not.toHaveBeenCalled();
  });

  it("puts a draft team into force and refreshes", async () => {
    vi.mocked(activateTeam).mockResolvedValue(makeTeam({ status: "active" }));
    render(<TeamLifecycleActions team={makeTeam({ status: "draft" })} />);

    fireEvent.click(screen.getByRole("button", { name: "Put into force" }));

    await waitFor(() => expect(activateTeam).toHaveBeenCalledWith(4));
    expect(refresh).toHaveBeenCalled();
  });

  it("offers retirement, not activation, once a team is in force", async () => {
    vi.mocked(deactivateTeam).mockResolvedValue(makeTeam({ status: "inactive" }));
    render(
      <TeamLifecycleActions
        team={makeTeam({ status: "active", is_effective: true })}
      />
    );

    expect(
      screen.queryByRole("button", { name: "Put into force" })
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retire team" }));

    await waitFor(() => expect(deactivateTeam).toHaveBeenCalledWith(4));
    expect(refresh).toHaveBeenCalled();
  });

  it("offers to bring a retired team back rather than hiding the action", async () => {
    render(<TeamLifecycleActions team={makeTeam({ status: "inactive" })} />);

    expect(
      screen.getByRole("button", { name: "Bring back into force" })
    ).toBeInTheDocument();
  });

  it("reports a plain failure without pretending it knows the reasons", async () => {
    vi.mocked(validateTeam).mockRejectedValue(new Error("Network unreachable."));
    render(<TeamLifecycleActions team={makeTeam()} />);

    fireEvent.click(screen.getByRole("button", { name: "Check readiness" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Network unreachable."
    );
  });
});
