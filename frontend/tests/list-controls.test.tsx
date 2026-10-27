import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FilterChips } from "@/components/ui/filter-chips";
import { ListSearch } from "@/components/ui/list-search";

describe("ListSearch", () => {
  it("reports every keystroke and names the box for assistive tech", () => {
    const onChange = vi.fn();
    render(
      <ListSearch value="" onChange={onChange} label="Search HR users" />
    );

    fireEvent.change(screen.getByRole("searchbox", { name: "Search HR users" }), {
      target: { value: "jane" },
    });

    expect(onChange).toHaveBeenCalledWith("jane");
  });

  it("offers a clear action only while there is something to clear", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <ListSearch value="" onChange={onChange} label="Search teams" />
    );

    expect(screen.queryByRole("button", { name: "Clear search" })).toBeNull();

    rerender(<ListSearch value="registry" onChange={onChange} label="Search teams" />);
    fireEvent.click(screen.getByRole("button", { name: "Clear search" }));

    expect(onChange).toHaveBeenCalledWith("");
  });
});

describe("FilterChips", () => {
  const options = [
    { value: "", label: "All accounts" },
    { value: "active", label: "Active only" },
    { value: "inactive", label: "Inactive only" },
  ] as const;

  it("marks exactly the current chip as pressed", () => {
    render(
      <FilterChips
        options={options}
        value="active"
        onChange={vi.fn()}
        label="Filter HR users by status"
      />
    );

    expect(
      screen.getByRole("button", { name: "Active only" })
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      screen.getByRole("button", { name: "All accounts" })
    ).toHaveAttribute("aria-pressed", "false");
  });

  it("hands the chosen value back to the host", () => {
    const onChange = vi.fn();
    render(
      <FilterChips
        options={options}
        value=""
        onChange={onChange}
        label="Filter HR users by status"
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Inactive only" }));

    expect(onChange).toHaveBeenCalledWith("inactive");
  });
});
