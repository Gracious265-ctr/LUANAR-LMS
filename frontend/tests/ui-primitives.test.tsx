import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Button } from "@/components/ui/button";
import { EmptyPanel, EmptyState, ErrorState } from "@/components/ui/states";
import { Toast, useToast } from "@/components/ui/toast";

function ToastHarness({ timeout }: { timeout?: number }) {
  const { toast, showToast, dismissToast } = useToast(timeout);
  return (
    <div>
      <button type="button" onClick={() => showToast("Saved")}>
        show
      </button>
      {toast && (
        <Toast tone="success" onDismiss={dismissToast}>
          {toast}
        </Toast>
      )}
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
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("dismisses early when the user closes it", () => {
    render(<ToastHarness />);
    fireEvent.click(screen.getByRole("button", { name: "show" }));
    fireEvent.click(screen.getByRole("button", { name: "Dismiss notification" }));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("restarts the countdown when a second message replaces the first", () => {
    function SequenceHarness() {
      const { toast, showToast } = useToast(1000);
      return (
        <div>
          <button type="button" onClick={() => showToast("First")}>
            first
          </button>
          <button type="button" onClick={() => showToast("Second")}>
            second
          </button>
          {toast && <Toast>{toast}</Toast>}
        </div>
      );
    }

    render(<SequenceHarness />);
    fireEvent.click(screen.getByRole("button", { name: "first" }));
    act(() => {
      vi.advanceTimersByTime(800);
    });
    fireEvent.click(screen.getByRole("button", { name: "second" }));
    expect(screen.getByRole("status")).toHaveTextContent("Second");

    // The first message's timer would have fired by now; the new one holds.
    act(() => {
      vi.advanceTimersByTime(800);
    });
    expect(screen.getByRole("status")).toHaveTextContent("Second");
    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("can render without an icon and without the enter animation", () => {
    render(
      <Toast tone="warning" hideIcon>
        Refreshed
      </Toast>
    );
    const toast = screen.getByRole("status");
    expect(toast).toHaveTextContent("Refreshed");
    expect(toast.querySelector("svg")).toBeNull();
    expect(toast.className).not.toContain("animate-toast-in");
  });
});

describe("EmptyState", () => {
  it("stays chrome-free so it can sit inside a bordered card", () => {
    render(<EmptyState title="No employees found" description="Try again." />);
    const state = screen.getByText("No employees found").parentElement;
    expect(state?.className).toContain("py-12");
    expect(state?.className).not.toContain("border");
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
});
