import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Button } from "@/components/ui/button";
import { EmptyPanel, EmptyState, ErrorState } from "@/components/ui/states";
import { Toast, Toaster, pushToast, useToast } from "@/components/ui/toast";

function ToastHarness() {
  const { showToast } = useToast();
  return (
    <div>
      <button type="button" onClick={() => showToast("Saved")}>
        show
      </button>
      <Toaster />
    </div>
  );
}

describe("Button", () => {
  it("defaults to type=button so it never submits a form by accident", () => {
    render(<Button>Save</Button>);
    expect(screen.getByRole("button", { name: "Save" })).toHaveAttribute(
      "type",
      "button"
    );
  });

  it("blocks clicks and reports busy while loading", () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        Saving
      </Button>
    );
    const button = screen.getByRole("button", { name: /Saving/ });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("applies the caller className last so it can override the variant", () => {
    render(<Button className="w-full">Wide</Button>);
    expect(screen.getByRole("button").className).toContain("w-full");
  });
});

describe("Toast", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("announces politely and auto-dismisses after the timeout", () => {
    render(<ToastHarness />);
    fireEvent.click(screen.getByRole("button", { name: "show" }));

    const toast = screen.getByRole("status");
    expect(toast).toHaveAttribute("aria-live", "polite");
    expect(toast).toHaveTextContent("Saved");

    act(() => {
      vi.advanceTimersByTime(4000);
    });
    // Kept mounted while the exit animation plays…
    expect(screen.getByRole("status")).toHaveClass(
      "motion-safe:animate-toast-out"
    );
    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("dismisses early when the user closes it", () => {
    render(<ToastHarness />);
    fireEvent.click(screen.getByRole("button", { name: "show" }));
    fireEvent.click(screen.getByRole("button", { name: "Dismiss notification" }));

    expect(screen.getByRole("status")).toHaveClass(
      "motion-safe:animate-toast-out"
    );
    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("stacks messages and runs each one's countdown independently", () => {
    render(<Toaster />);
    act(() => pushToast("First"));
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    act(() => pushToast("Second"));

    expect(screen.getAllByRole("status")).toHaveLength(2);

    // First expires 4000ms after it was pushed (plus its 200ms exit)…
    act(() => {
      vi.advanceTimersByTime(3200);
    });
    expect(screen.queryByText("First")).not.toBeInTheDocument();
    expect(screen.getByText("Second")).toBeInTheDocument();

    // …and Second, pushed a second later, outlives it by that same second.
    act(() => {
      vi.advanceTimersByTime(800);
    });
    expect(screen.getByText("Second")).toHaveClass(
      "motion-safe:animate-toast-out"
    );
    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("replaces an identical message instead of stacking a duplicate", () => {
    render(<Toaster />);
    act(() => pushToast("Saved"));
    act(() => pushToast("Saved"));

    expect(screen.getAllByRole("status")).toHaveLength(1);
  });

  it("stacks in the bottom-right corner", () => {
    render(<Toaster />);
    act(() => pushToast("Saved"));

    const region = screen.getByLabelText("Notifications");
    expect(region.className).toContain("fixed");
    expect(region.className).toContain("right-4");
    expect(region.className).toContain("bottom-4");
    expect(region.className).toContain("z-toast");
  });

  it("renders a tone surface with its icon and the enter animation", () => {
    render(<Toast tone="warning">Refreshed</Toast>);
    const toast = screen.getByRole("status");
    expect(toast).toHaveTextContent("Refreshed");
    expect(toast.querySelector("svg")).not.toBeNull();
    expect(toast.className).toContain("motion-safe:animate-toast-in");
  });

  it("can render without an icon and swaps in the exit animation", () => {
    render(
      <Toast tone="warning" hideIcon exiting>
        Refreshed
      </Toast>
    );
    const toast = screen.getByRole("status");
    expect(toast.querySelector("svg")).toBeNull();
    expect(toast.className).toContain("motion-safe:animate-toast-out");
  });
});

describe("EmptyState", () => {
  it("stays chrome-free so it can sit inside a bordered card", () => {
    render(<EmptyState title="No employees found" description="Try again." />);
    const state = screen.getByText("No employees found").parentElement;
    expect(state?.className).toContain("py-12");
    expect(state?.className).not.toContain("border");
  });

  it("shrink-wraps its icon so it centres instead of pinning left", () => {
    // Preflight renders svg as display:block, which ignores text-align; only a
    // shrink-wrapped wrapper lets mx-auto actually centre the icon.
    render(
      <EmptyState
        icon={<svg data-testid="state-icon" />}
        title="No employees found"
      />
    );
    const wrapper = screen.getByTestId("state-icon").parentElement;
    expect(wrapper?.className).toContain("mx-auto");
    expect(wrapper?.className).toContain("w-fit");
  });

  it("keeps the page heading level the caller asked for", () => {
    render(
      <section>
        <h2>My Drafts</h2>
        <EmptyState title="No drafts yet" titleAs="h3" />
      </section>
    );
    expect(
      screen.getByRole("heading", { level: 3, name: "No drafts yet" })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { level: 2, name: "No drafts yet" })
    ).toBeNull();
  });
});

describe("EmptyPanel", () => {
  it("adds exactly one layer of card chrome and keeps the action", () => {
    render(
      <EmptyPanel
        title="No drafts yet"
        description="Start a new leave application to see it here."
        action={<Button>New Application</Button>}
      />
    );
    const panel = screen.getByRole("heading", { level: 2, name: "No drafts yet" }).parentElement;
    expect(panel?.className).toContain("border-border-default");
    expect(panel?.className).toContain("p-10");
    expect(panel?.className).not.toContain("py-12");
    expect(screen.getByRole("button", { name: "New Application" })).toBeInTheDocument();
  });
});

describe("ErrorState", () => {
  it("announces the failure and offers the retry", () => {
    const onRetry = vi.fn();
    render(<ErrorState message="Network down" onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Network down");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("shrink-wraps its icon the same way as the empty states", () => {
    render(
      <ErrorState
        message="Network down"
        icon={<svg data-testid="error-icon" />}
      />
    );
    const wrapper = screen.getByTestId("error-icon").parentElement;
    expect(wrapper?.className).toContain("mx-auto");
    expect(wrapper?.className).toContain("w-fit");
  });
});
