import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CampusForm } from "@/components/hr/campus-form";
import { makeCampus } from "@/lib/teams/__fixtures__";
import { createCampus, updateCampus } from "@/lib/teams-client";

const refresh = vi.fn();
const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh, push }),
}));

vi.mock("@/lib/teams-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/teams-client")>();
  return { ...actual, createCampus: vi.fn(), updateCampus: vi.fn() };
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe("CampusForm", () => {
  it("writes a campus with name, code and description", async () => {
    vi.mocked(createCampus).mockResolvedValue(
      makeCampus({ id: 2, name: "Bunda Campus", code: "bunda-campus" })
    );
    render(<CampusForm />);

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Bunda Campus" },
    });
    fireEvent.change(screen.getByLabelText("Description"), {
      target: { value: "The main teaching campus" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create campus" }));

    await waitFor(() =>
      expect(createCampus).toHaveBeenCalledWith({
        name: "Bunda Campus",
        code: "bunda-campus",
        description: "The main teaching campus",
      })
    );
  });

  it("saves an existing campus rather than creating a second one", async () => {
    vi.mocked(updateCampus).mockResolvedValue(
      makeCampus({ id: 2, name: "Renamed Campus", code: "renamed-campus" })
    );

    const campus = makeCampus({ id: 2, name: "Bunda Campus", code: "bunda" });
    render(<CampusForm campus={campus} />);

    expect(
      screen.getByRole("button", { name: "Save campus" })
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Renamed Campus" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save campus" }));

    await waitFor(() =>
      expect(updateCampus).toHaveBeenCalledWith(2, {
        name: "Renamed Campus",
        code: "renamed-campus",
        description: "",
      })
    );
    expect(createCampus).not.toHaveBeenCalled();
  });

  it("keeps the form open and explains a refusal", async () => {
    vi.mocked(createCampus).mockRejectedValue(
      new Error("A campus with that code already exists.")
    );
    render(<CampusForm />);

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Bunda Campus" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create campus" }));

    expect(
      await screen.findByText("A campus with that code already exists.")
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toBeInTheDocument();
    expect(refresh).not.toHaveBeenCalled();
  });

  it("navigates to where it was asked to go after a save", async () => {
    vi.mocked(createCampus).mockResolvedValue(
      makeCampus({ id: 2, name: "Bunda Campus", code: "bunda-campus" })
    );
    render(<CampusForm returnTo="/dashboard/hr-admin/campuses" />);

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Bunda Campus" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create campus" }));

    await waitFor(() =>
      expect(push).toHaveBeenCalledWith("/dashboard/hr-admin/campuses")
    );
  });

  it("goes nowhere when cancel is pressed, and creates nothing", () => {
    render(<CampusForm />);

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(createCampus).not.toHaveBeenCalled();
    expect(push).toHaveBeenCalledWith("/dashboard/hr-admin/campuses");
  });
});
