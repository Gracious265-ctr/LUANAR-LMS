"use client";

import Link from "next/link";
import { Card } from "@/components/ui/card";
import { APPS_REGISTRY, type AppKey } from "@/lib/apps-registry";

type AppCardProps = {
  keyName: string;
  badge: {
    count?: number;
    label?: string;
    tone?: string;
  } | null;
};

export function AppCard({ keyName, badge }: AppCardProps) {
  const key = keyName as AppKey;
  const app = APPS_REGISTRY[key];
  if (!app) return null;

  const Icon = app.icon;

  return (
    <Link href={app.route} className="block">
      <Card className="flex aspect-square flex-col p-3 transition-shadow hover:shadow-md sm:p-6">
        <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center sm:gap-4">
          <div className="flex size-11 items-center justify-center rounded-lg bg-primary/10 text-primary sm:size-12">
            <Icon className="size-6 sm:size-7" />
          </div>

          <div className="w-full">
            <div className="flex flex-wrap items-center justify-center gap-x-1.5 gap-y-1">
              <h3 className="text-base font-semibold leading-tight sm:text-lg">
                {app.name}
              </h3>
              {badge && badge.count ? (
                <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700">
                  {badge.count} {badge.label || ""}
                </span>
              ) : null}
            </div>

            <p className="mt-1 line-clamp-2 text-sm leading-snug text-muted-foreground sm:line-clamp-3">
              {app.description}
            </p>
          </div>
        </div>
      </Card>
    </Link>
  );
}
