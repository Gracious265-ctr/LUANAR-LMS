"use client";

import { useEffect, useState } from "react";
import { AppCard } from "./app-card";
import { getLauncherApps, type LauncherResponse } from "@/lib/launcher";
import { APPS_REGISTRY, type AppKey } from "@/lib/apps-registry";

export function AppLauncherGrid() {
  const [data, setData] = useState<LauncherResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getLauncherApps()
      .then(setData)
      .catch(() => setData({ apps: [] }))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-24 bg-muted rounded-md animate-pulse" />
        ))}
      </div>
    );
  }

  const apps = (data?.apps || [])
    .map((a) => {
      const key = a.key as AppKey;
      if (!(key in APPS_REGISTRY)) {
        // A key the registry does not know is dropped, so a module renamed on
        // one side of the API would lose its card with nothing failing. Say so
        // in development instead of hiding it; see backend/launcher/services.py
        // and APPS_REGISTRY in lib/apps-registry.ts.
        if (process.env.NODE_ENV !== "production") {
          console.warn(
            `Launcher returned unknown app key "${a.key}". ` +
              "Add it to APPS_REGISTRY in frontend/lib/apps-registry.ts."
          );
        }
        return null;
      }
      return { ...a, key };
    })
    .filter(Boolean) as Array<{
    key: AppKey;
    badge: { count?: number; label?: string; tone?: string } | null;
  }>;

  if (apps.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-sm font-medium text-text-primary">
          No apps available for your role
        </p>
        <p className="mt-1 text-sm text-text-muted">
          Contact your administrator if you need access.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-2 lg:grid-cols-4 sm:gap-5">
      {apps.map((app) => (
        <AppCard key={app.key} keyName={app.key} badge={app.badge} />
      ))}
    </div>
  );
}
