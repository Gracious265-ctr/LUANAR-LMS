import { cn } from "@/lib/utils";

import { Button } from "./button";

type EmptyStateBodyProps = {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  /** Keeps the page's heading order intact when a page already uses an h2. */
  titleAs?: "h1" | "h2" | "h3" | "h4";
};

/** The copy and controls of an empty state, without any surrounding chrome. */
function EmptyStateBody({
  icon,
  title,
  description,
  action,
  titleAs: Title = "h2",
}: EmptyStateBodyProps) {
  return (
    <>
      {icon && (
        <span className="mx-auto mb-4 block" aria-hidden="true">
          {icon}
        </span>
      )}
      <Title className="text-base font-semibold text-text-primary">
        {title}
      </Title>
      {description && (
        <p className="mx-auto mt-1 max-w-sm text-sm text-text-secondary">
          {description}
        </p>
      )}
      {action && (
        <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
          {action}
        </div>
      )}
    </>
  );
}

/**
 * Empty state for a list or table that has nothing to show.
 *
 * Deliberately chrome-free: these tables render inside an already-bordered
 * card, so this supplies only the copy and spacing while the card supplies the
 * border. Use `EmptyPanel` when the state is the whole surface.
 */
export function EmptyState({
  className,
  ...props
}: EmptyStateBodyProps & { className?: string }) {
  return (
    <div className={cn("py-12 text-center", className)}>
      <EmptyStateBody {...props} />
    </div>
  );
}

/** Empty state that is the whole surface: adds the card chrome. */
export function EmptyPanel({
  className,
  ...props
}: EmptyStateBodyProps & { className?: string }) {
  return (
    <div
      className={cn(
        "rounded-xl border border-border-default bg-surface-card p-10 text-center shadow-subtle",
        className
      )}
    >
      <EmptyStateBody {...props} />
    </div>
  );
}

/** Error state: says what failed and offers the one useful next step. */
export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
  retryLabel = "Try again",
  icon,
  children,
  className,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
  icon?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "rounded-xl border border-border-default bg-surface-card p-10 text-center shadow-subtle",
        className
      )}
    >
      {icon && (
        <span className="mx-auto mb-4 block" aria-hidden="true">
          {icon}
        </span>
      )}
      <h2 className="text-base font-semibold text-text-primary">{title}</h2>
      <p className="mx-auto mt-1 max-w-sm text-sm text-text-secondary">
        {message}
      </p>
      {children}
      {onRetry && (
        <div className="mt-5 flex justify-center">
          <Button variant="primary" size="md" onClick={onRetry}>
            {retryLabel}
          </Button>
        </div>
      )}
    </div>
  );
}

/** Inline dismissible alert, for errors raised next to the thing that failed. */
export function Alert({
  tone = "error",
  title,
  children,
  onDismiss,
  dismissLabel = "Dismiss",
  className,
}: {
  tone?: "error" | "info" | "success";
  title?: string;
  children: React.ReactNode;
  onDismiss?: () => void;
  dismissLabel?: string;
  className?: string;
}) {
  const tones = {
    error: "border-border-error bg-status-rejected-subtle",
    info: "border-brand-primary-border bg-brand-primary-subtle",
    success: "border-brand-secondary-border bg-brand-secondary-subtle",
  } as const;

  return (
    <div
      role="alert"
      className={cn(
        "flex items-start justify-between gap-3 rounded-lg border p-4",
        tones[tone],
        className
      )}
    >
      <div className="min-w-0">
        {title && (
          <p className="text-sm font-semibold text-text-primary">{title}</p>
        )}
        <div className={cn("text-sm text-text-secondary", title && "mt-1")}>
          {children}
        </div>
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 text-xs font-medium text-text-muted transition-colors duration-fast ease-standard hover:text-text-primary focus-ring"
        >
          {dismissLabel}
        </button>
      )}
    </div>
  );
}
