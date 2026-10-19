"use client";

import React, { memo, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronLeft, Menu, X } from "lucide-react";

import { useIsMobile } from "@/lib/hooks/useIsMobile";
import { cn } from "@/lib/utils";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogDescription,
  DialogOverlay,
  DialogPortal,
  DialogSurface,
  DialogTitle,
} from "@/components/ui/dialog";

export type NavItem = {
  href: string;
  label: string;
  icon?: React.ComponentType<{ className?: string }>;
};

export type ModuleShellProps = {
  children: React.ReactNode;
  navItems: NavItem[];
  moduleName: string;
};

const NAV_ID = "module-nav";

/**
 * The shell shared by the restructured module roots (`/leave`, `/approvals`,
 * `/organisation`, `/documents`, `/hr-admin`).
 *
 * It deliberately mirrors `DashboardShell`'s language — the same rail width,
 * borders, brand-tinted active link, header and padded, scrolling main — so the
 * module pages read as the same product as the legacy `/dashboard` tree. The
 * difference is scope: the rail lists only this module's destinations and the
 * header carries the module name, with a way back to the app launcher.
 *
 * On a phone the rail collapses into a Radix dialog drawer and the header gains
 * a menu trigger, exactly as the dashboard does, so nothing is unreachable.
 */
export function ModuleShell({
  children,
  navItems,
  moduleName,
}: ModuleShellProps) {
  const pathname = usePathname();
  const isMobile = useIsMobile();
  const [drawerOpen, setDrawerOpen] = useState(false);

  // A drawer left open across a navigation would sit on top of the page the
  // user just asked for. Radix handles Escape and the backdrop; the route
  // change it cannot see is closed here, during render, so it closes in the
  // same paint as the new page rather than flashing the old route's nav over
  // it. (Same pattern as `DashboardShell`.)
  const [navPath, setNavPath] = useState(pathname);
  if (pathname !== navPath) {
    setNavPath(pathname);
    setDrawerOpen(false);
  }

  const nav = (
    <>
      <ModuleTitle
        moduleName={moduleName}
        onDismiss={() => setDrawerOpen(false)}
      />
      <NavLinks currentPath={pathname} navItems={navItems} />
    </>
  );

  return (
    <div className="flex h-screen bg-surface-page text-text-primary">
      {/* Hidden on a phone rather than rendered narrow: a column of icons
          cannot be labelled, and the drawer already carries the same nav. */}
      <div className={cn("hidden shrink-0 md:block", isMobile && "md:hidden")}>
        <Sidebar
          id={NAV_ID}
          moduleName={moduleName}
          navItems={navItems}
          currentPath={pathname}
        />
      </div>

      <Drawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        moduleName={moduleName}
        nav={nav}
      />

      <div className="flex flex-1 flex-col overflow-hidden">
        <Header
          moduleName={moduleName}
          navOpen={drawerOpen}
          onOpenNav={() => setDrawerOpen(true)}
        />
        <main className="flex-1 overflow-auto p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}

const Sidebar = memo(function Sidebar({
  id,
  moduleName,
  navItems,
  currentPath,
}: {
  id: string;
  moduleName: string;
  navItems: NavItem[];
  currentPath: string;
}) {
  return (
    <nav
      id={id}
      className="sticky top-0 flex h-screen w-64 shrink-0 flex-col border-r border-border-default bg-surface-card p-2"
    >
      <ModuleTitle moduleName={moduleName} />
      <NavLinks currentPath={currentPath} navItems={navItems} />
    </nav>
  );
});

const ModuleTitle = memo(function ModuleTitle({
  moduleName,
  onDismiss,
}: {
  moduleName: string;
  /** Supplied in the drawer, which has no rail to collapse but can be closed. */
  onDismiss?: () => void;
}) {
  return (
    <div className="mb-4 shrink-0 border-b border-border-default pb-4">
      <div className="flex items-center justify-between gap-2 px-2">
        <Link
          href="/"
          className="focus-ring inline-flex items-center gap-1.5 rounded-sm text-xs font-medium text-text-muted transition-colors hover:text-text-primary"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          All Apps
        </Link>
        {onDismiss && (
          <Button
            type="button"
            onClick={onDismiss}
            aria-label="Close navigation"
            title="Close navigation"
            variant="ghost"
            size="icon"
            className="h-auto w-auto p-1.5"
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>

      <div className="mt-3 flex items-center gap-2 px-2">
        <div className="grid size-8 shrink-0 place-content-center rounded-lg bg-brand-primary text-sm font-medium text-brand-primary-foreground">
          {moduleName.charAt(0)}
        </div>
        <span className="truncate text-sm font-semibold text-text-primary">
          {moduleName}
        </span>
      </div>
    </div>
  );
});

const NavLinks = memo(function NavLinks({
  currentPath,
  navItems,
}: {
  currentPath: string;
  navItems: NavItem[];
}) {
  return (
    <div className="min-h-0 flex-1 space-y-1 overflow-y-auto pb-2">
      {navItems.map((item) => {
        const Icon = item.icon;
        const isSelected = currentPath === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={isSelected ? "page" : undefined}
            className={cn(
              "relative flex h-11 w-full items-center rounded-md transition-colors duration-200",
              isSelected
                ? "border-l-2 border-brand-primary bg-brand-primary-subtle text-brand-primary shadow-sm"
                : "text-text-secondary hover:bg-surface-hover hover:text-text-primary"
            )}
          >
            <div className="grid h-full w-12 place-content-center">
              {Icon && <Icon className="h-4 w-4" />}
            </div>
            <span className="text-sm font-medium">{item.label}</span>
          </Link>
        );
      })}
    </div>
  );
});

const Header = memo(function Header({
  moduleName,
  onOpenNav,
  navOpen,
}: {
  moduleName: string;
  onOpenNav: () => void;
  /** Mirrored onto the trigger's `aria-expanded` so the attribute stays honest. */
  navOpen: boolean;
}) {
  return (
    <header className="z-header flex items-center justify-between gap-3 border-b border-border-default bg-surface-card px-4 py-3 sm:px-6 sm:py-4">
      <div className="flex min-w-0 items-center gap-3">
        <Button
          type="button"
          onClick={onOpenNav}
          aria-label="Open navigation"
          aria-expanded={navOpen}
          aria-controls={NAV_ID}
          title="Open navigation"
          variant="ghost"
          size="icon"
          className="size-10 shrink-0 md:hidden"
        >
          <Menu className="h-5 w-5" />
        </Button>

        <h1 className="truncate text-lg font-semibold tracking-tight text-text-primary sm:text-xl">
          {moduleName}
        </h1>
      </div>

      <div className="flex shrink-0 items-center gap-3 sm:gap-4">
        <ThemeToggle />
      </div>
    </header>
  );
});

const Drawer = memo(function Drawer({
  open,
  onOpenChange,
  moduleName,
  nav,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  moduleName: string;
  nav: React.ReactNode;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPortal>
        <DialogOverlay className="md:hidden" />
        <DialogSurface
          id={NAV_ID}
          className={cn(
            "fixed inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col md:hidden",
            "border-r border-border-default bg-surface-card p-2 shadow-modal",
            "data-[state=open]:animate-in data-[state=open]:slide-in-from-left-2",
            "data-[state=closed]:animate-out data-[state=closed]:slide-out-to-left-2"
          )}
        >
          <DialogTitle className="sr-only">{moduleName} navigation</DialogTitle>
          <DialogDescription className="sr-only">
            {moduleName} module.
          </DialogDescription>
          {nav}
        </DialogSurface>
      </DialogPortal>
    </Dialog>
  );
});
