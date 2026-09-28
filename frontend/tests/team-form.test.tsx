import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TeamForm } from "@/components/hr/team-form";
import type { Campus } from "@/lib/teams";
import { makeCampus, makeTeam } from "@/lib/teams/__fixtures__";
import { createTeam, updateTeam } from "@/lib/teams-client";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

vi.mock("@/lib/teams-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/teams-client")>();
  return { ...actual, createTeam: vi.fn(), updateTeam: vi.fn() };
});

const campuses: Campus[] = [
  makeCampus(),
  makeCampus({ id: 2, name: "Bunda Campus", code: "bunda" }),
];

const workflows = [
  { id: 1, name: "Academic approval" },
  { id: 2, name: "Administrative approval" },
];

beforeEach(() => {
  vi.clearAllMocks();
});

describe("TeamForm", () => {
  it("sends a null campus and workflow when neither is chosen", async () => {
    vi.mocked(createTeam).mockResolvedValue(makeTeam());
    render(<TeamForm campuses={campuses} workflows={workflows} />);

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Registry" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create team" }));

    await waitFor(() =>
      expect(createTeam).toHaveBeenCalledWith({
        name: "Registry",
        description: "",
        campus: null,
        workflow: null,
        is_active: true,
      })
    );
    expect(push).toHaveBeenCalledWith("/dashboard/hr-admin/teams");
    expect(refresh).toHaveBeenCalled();
  });

  it("sends the chosen campus and workflow as ids", async () => {
    vi.mocked(createTeam).mockResolvedValue(makeTeam());
    render(<TeamForm campuses={campuses} workflows={workflows} />);

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Registry" },
    });
    fireEvent.change(screen.getByLabelText("Campus"), {
      target: { value: "1" },
    });
    fireEvent.change(screen.getByLabelText("Approval workflow"), {
      target: { value: "2" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create team" }));

    await waitFor(() =>
      expect(createTeam).toHaveBeenCalledWith(
        expect.objectContaining({ campus: 1, workflow: 2 })
      )
    );
  });

  it("can retire a team by clearing its active box", async () => {
    vi.mocked(createTeam).mockResolvedValue(makeTeam());
    render(<TeamForm campuses={campuses} workflows={workflows} />);

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Registry" },
    });
    fireEvent.click(screen.getByLabelText("Active team"));
    fireEvent.click(screen.getByRole("button", { name: "Create team" }));

    await waitFor(() =>
      expect(createTeam).toHaveBeenCalledWith(
        expect.objectContaining({ is_active: false })
      )
    );
  });

  it("updates the team it was given, prefilled, instead of creating one", () => {
    render(
      <TeamForm
        team={makeTeam({
          campus: 2,
          campus_name: "Bunda Campus",
          workflow: 2,
          workflow_name: "Administrative approval",
        })}
        campuses={campuses}
        workflows={workflows}
      />
    );

    expect(screen.getByLabelText("Name")).toHaveValue(
      "Bunda College Faculty"
    );
    expect(screen.getByLabelText("Campus")).toHaveValue("2");
    expect(screen.getByLabelText("Approval workflow")).toHaveValue("2");
    expect(
      screen.getByRole("button", { name: "Save changes" })
    ).toBeInTheDocument();
  });

  it("updates the team it was given on submit", async () => {
    vi.mocked(updateTeam).mockResolvedValue(makeTeam());
    render(
      <TeamForm
        team={makeTeam({
          campus: 2,
          campus_name: "Bunda Campus",
          workflow: 2,
          workflow_name: "Administrative approval",
        })}
        campuses={campuses}
        workflows={workflows}
      />
    );

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Bunda Faculty" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(updateTeam).toHaveBeenCalledWith(
        4,
        expect.objectContaining({ name: "Bunda Faculty" })
      )
    );
    expect(createTeam).not.toHaveBeenCalled();
  });

  it("offers the institution-wide workflow as the no-choice default", () => {
    render(<TeamForm campuses={campuses} workflows={workflows} />);

    expect(
      screen.getByRole("option", { name: "Institution-wide workflow" })
    ).toBeInTheDocument();
  });

  it("shows why the backend refused the team and stays on the form", async () => {
    vi.mocked(createTeam).mockRejectedValue(
      new Error("A team with that name already exists.")
    );
    render(<TeamForm campuses={campuses} workflows={workflows} />);

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Registry" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create team" }));

    expect(
      await screen.findByText("A team with that name already exists.")
    ).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });
});
