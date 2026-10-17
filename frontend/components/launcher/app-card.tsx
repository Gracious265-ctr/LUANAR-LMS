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
      <Card className="hover:shadow-md transition-shadow">
        <div className="p-6 flex items-start gap-4">
          <div className="w-10 h-10 rounded-md bg-primary/10 flex items-center justify-center text-primary">
            <Icon className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <div className="flex items-start justify-between">
              <h3 className="font-semibold">{app.name}</h3>
              {badge && badge.count ? (
                <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">
                  {badge.count} {badge.label || ""}
                </span>
              ) : null}
            </div>
            <p className="text-sm text-muted-foreground mt-1">{app.description}</p>
          </div>
        </div>
      </Card>
    </Link>
  );
}
