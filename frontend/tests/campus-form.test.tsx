import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CampusForm } from "@/components/hr/campus-form";
import { makeCampus } from "@/lib/teams/__fixtures__";
import { createCampus } from "@/lib/teams-client";

const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh }),
}));

vi.mock("@/lib/teams-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/teams-client")>();
  return { ...actual, createCampus: vi.fn() };
});

const campuses = [makeCampus()];

function openForm() {
  fireEvent.click(screen.getByRole("button", { name: "Add a campus" }));
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("CampusForm", () => {
  it("says a campus is optional when there are none", () => {
    render(<CampusForm campuses={[]} />);

    expect(
      screen.getByText("No campuses yet. A campus is optional on a team.")
    ).toBeInTheDocument();
  });

  it("lists existing campuses by name and code", () => {
    render(<CampusForm campuses={campuses} />);

    expect(screen.getByText("Main Campus")).toBeInTheDocument();
    expect(screen.getByText("main")).toBeInTheDocument();
  });

  it("stays closed until asked for", () => {
    render(<CampusForm campuses={campuses} />);

    expect(screen.queryByLabelText("Code")).not.toBeInTheDocument();

    openForm();

    expect(screen.getByLabelText("Code")).toBeInTheDocument();
  });

  it("creates a campus and closes itself again", async () => {
    vi.mocked(createCampus).mockResolvedValue(
      makeCampus({ id: 2, name: "Bunda Campus", code: "bunda" })
    );
    render(<CampusForm campuses={campuses} />);

    openForm();
    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Bunda Campus" },
    });
    fireEvent.change(screen.getByLabelText("Code"), {
      target: { value: "bunda" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create campus" }));

    await waitFor(() =>
      expect(createCampus).toHaveBeenCalledWith({
        name: "Bunda Campus",
        code: "bunda",
        description: "",
      })
    );
    expect(screen.queryByLabelText("Code")).not.toBeInTheDocument();
    expect(refresh).toHaveBeenCalled();
  });

  it("keeps the form open and explains a refusal", async () => {
    vi.mocked(createCampus).mockRejectedValue(
      new Error("A campus with that code already exists.")
    );
    render(<CampusForm campuses={campuses} />);

    openForm();
    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Bunda Campus" },
    });
    fireEvent.change(screen.getByLabelText("Code"), {
      target: { value: "bunda" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create campus" }));

    expect(
      await screen.findByText("A campus with that code already exists.")
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Code")).toBeInTheDocument();
    expect(refresh).not.toHaveBeenCalled();
  });

  it("closes without creating anything when cancelled", () => {
    render(<CampusForm campuses={campuses} />);

    openForm();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(createCampus).not.toHaveBeenCalled();
    expect(screen.queryByLabelText("Code")).not.toBeInTheDocument();
  });
});
