import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Avatar } from "@/components/ui/Avatar";

describe("Avatar", () => {
  it("renders up to two initials from the person's name", () => {
    render(<Avatar name="Jane Banda" userId="u-1" />);

    expect(screen.getByText("JB")).toBeInTheDocument();
  });

  it("renders one initial for a single-word name", () => {
    render(<Avatar name="chirwa" userId="u-2" />);

    expect(screen.getByText("C")).toBeInTheDocument();
  });

  it("renders a placeholder instead of crashing on an empty name", () => {
    render(<Avatar name="   " userId="u-3" />);

    expect(screen.getByText("?")).toBeInTheDocument();
  });

  it("renders the same colour for the same user id on every render", () => {
    const first = render(<Avatar name="Jane Banda" userId="42" />);
    const firstClass = (first.container.firstChild as HTMLElement).className;

    const second = render(<Avatar name="Jane Banda" userId="42" />);
    const secondClass = (second.container.firstChild as HTMLElement).className;

    expect(secondClass).toBe(firstClass);
    expect(firstClass).toMatch(/bg-\w+-100/);
  });

  it("applies the size scale", () => {
    const { container } = render(
      <Avatar name="Jane Banda" userId="u-1" size="sm" />
    );

    expect((container.firstChild as HTMLElement).className).toContain(
      "h-6 w-6 text-xs"
    );
  });

  it("renders the photo instead of initials when a src is given", () => {
    const { container } = render(
      <Avatar
        name="Jane Banda"
        userId="u-1"
        src="https://cdn.example.com/jane.jpg"
      />
    );

    const img = container.querySelector("img");
    expect(img).not.toBeNull();
    expect(img?.getAttribute("src")).toBe(
      "https://cdn.example.com/jane.jpg"
    );
    expect(screen.queryByText("JB")).toBeNull();
  });
});
