import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CampusForm, CampusQuickAdd } from "@/components/hr/campus-form";
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

const campuses = [makeCampus()];

beforeEach(() => {
  vi.clearAllMocks();
});

describe("CampusForm", () => {
  it("writes a campus with name, code and description", async () => {
    vi.mocked(createCampus).mockResolvedValue(
      makeCampus({ id: 2, name: "Bunda Campus", code: "bunda" })
    );
    render(<CampusForm />);

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Bunda Campus" },
    });
    fireEvent.change(screen.getByLabelText("Code"), {
      target: { value: "bunda" },
    });
    fireEvent.change(screen.getByLabelText("Description"), {
      target: { value: "The main teaching campus" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create campus" }));

    await waitFor(() =>
      expect(createCampus).toHaveBeenCalledWith({
        name: "Bunda Campus",
        code: "bunda",
        description: "The main teaching campus",
      })
    );
  });

  it("saves an existing campus rather than creating a second one", async () => {
    vi.mocked(updateCampus).mockResolvedValue(
      makeCampus({ id: 2, name: "Renamed Campus", code: "bunda" })
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
        code: "bunda",
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

  it("navigates to where it was asked to go after a save", async () => {
    vi.mocked(createCampus).mockResolvedValue(
      makeCampus({ id: 2, name: "Bunda Campus", code: "bunda" })
    );
    render(<CampusForm returnTo="/organisation/campuses" />);

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Bunda Campus" },
    });
    fireEvent.change(screen.getByLabelText("Code"), {
      target: { value: "bunda" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create campus" }));

    await waitFor(() =>
      expect(push).toHaveBeenCalledWith("/organisation/campuses")
    );
  });

  it("goes nowhere when cancel is pressed, and creates nothing", () => {
    render(<CampusForm />);

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(createCampus).not.toHaveBeenCalled();
    expect(push).toHaveBeenCalledWith("/organisation/campuses");
  });
});

describe("CampusQuickAdd", () => {
  it("says a campus is required for an academic team when there are none", () => {
    render(<CampusQuickAdd campuses={[]} />);

    expect(
      screen.getByText("No campuses yet. A campus is required for an academic team.")
    ).toBeInTheDocument();
  });

  it("lists existing campuses by name and code, linked to their page", () => {
    render(<CampusQuickAdd campuses={campuses} />);

    expect(screen.getByText("Main Campus")).toBeInTheDocument();
    expect(screen.getByText("main")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Main Campus/ })
    ).toHaveAttribute("href", "/organisation/campuses/1");
  });

  it("stays closed until asked for", () => {
    render(<CampusQuickAdd campuses={campuses} />);

    expect(screen.queryByLabelText("Code")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Add a campus" }));

    expect(screen.getByLabelText("Code")).toBeInTheDocument();
  });

  it("creates a campus and closes itself again", async () => {
    vi.mocked(createCampus).mockResolvedValue(
      makeCampus({ id: 2, name: "Bunda Campus", code: "bunda" })
    );
    render(<CampusQuickAdd campuses={campuses} />);

    fireEvent.click(screen.getByRole("button", { name: "Add a campus" }));
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
    // The quick add stays on the page that asked for the campus: a campus is
    // usually created because a team form needed one, and leaving that form
    // would throw the work away.
    expect(screen.queryByLabelText("Code")).not.toBeInTheDocument();
    expect(refresh).toHaveBeenCalled();
    expect(push).not.toHaveBeenCalled();
  });

  it("closes without creating anything when cancelled", () => {
    render(<CampusQuickAdd campuses={campuses} />);

    fireEvent.click(screen.getByRole("button", { name: "Add a campus" }));
    // Two cancel controls once open: the form's own, and the quick add's outer
    // one. Either closes the panel; the assertion is that nothing is created.
    fireEvent.click(screen.getAllByRole("button", { name: "Cancel" })[0]);

    expect(createCampus).not.toHaveBeenCalled();
    expect(screen.queryByLabelText("Code")).not.toBeInTheDocument();
  });
});
