import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RouteError } from "@/components/feedback/route-error";
import {
  DetailPageSkeleton,
  FormPageSkeleton,
  ListPageSkeleton,
  PageSkeleton,
} from "@/components/feedback/route-skeletons";
import NotFound from "@/app/not-found";

describe("RouteError", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows a retry action that re-renders the segment", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const retry = vi.fn();
    render(
      <RouteError error={Object.assign(new Error("boom"), {})} retry={retry} />
    );

    expect(screen.getByRole("alert")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it("surfaces the digest as a support reference and never the raw message", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <RouteError
        error={Object.assign(new Error("secret internal detail"), {
          digest: "abc123",
        })}
        retry={() => {}}
      />
    );

    expect(screen.getByText(/Reference: abc123/)).toBeInTheDocument();
    expect(screen.queryByText(/secret internal detail/)).not.toBeInTheDocument();
  });
});

describe("route skeletons", () => {
  it("announce themselves as busy and hide decorative blocks", () => {
    const { container } = render(
      <PageSkeleton label="Loading employees">
        <ListPageSkeleton label="unused" rows={0} />
      </PageSkeleton>
    );

    const region = container.querySelector('[role="status"]');
    expect(region).toHaveAttribute("aria-busy", "true");
    expect(region).toHaveAttribute("aria-label", "Loading employees");
  });

  it("size a list skeleton to the requested number of rows", () => {
    const { container } = render(
      <ListPageSkeleton label="Loading employees" rows={5} columns={3} />
    );

    // The table card's first child is the header row, then one child per row.
    const card = container.querySelector('[role="status"]')!.lastElementChild!;
    expect(card.children).toHaveLength(1 + 5);
  });

  it("render form and detail placeholders", () => {
    const { container: form } = render(
      <FormPageSkeleton label="Loading form" fields={4} />
    );
    expect(form.querySelector('[role="status"]')).toBeInTheDocument();

    const { container: detail } = render(
      <DetailPageSkeleton label="Loading employee" fields={6} />
    );
    expect(detail.querySelector('[role="status"]')).toBeInTheDocument();
  });
});

describe("NotFound", () => {
  it("explains the miss and offers a way back", () => {
    render(<NotFound />);
    expect(
      screen.getByRole("heading", { name: /could not find that page/i })
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /back to dashboard/i })).toHaveAttribute(
      "href",
      "/dashboard"
    );
  });
});
