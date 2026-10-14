"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { cn } from "@/lib/utils";

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

export function ModuleShell({ children, navItems, moduleName }: ModuleShellProps) {
  const pathname = usePathname();

  return (
    <div className="flex min-h-screen">
      <aside className="w-64 border-r bg-card flex flex-col">
        <div className="p-4 border-b">
          <Link href="/" className="flex items-center gap-2 text-sm hover:underline">
            <ChevronLeft className="w-4 h-4" />
            <span>← All Apps</span>
          </Link>
          <div className="mt-2 font-semibold">{moduleName}</div>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2 px-3 py-2 rounded-md text-sm hover:bg-accent",
                  isActive && "bg-accent"
                )}
              >
                {Icon && <Icon className="w-4 h-4" />}
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </aside>
      <main className="flex-1">{children}</main>
    </div>
  );
}
