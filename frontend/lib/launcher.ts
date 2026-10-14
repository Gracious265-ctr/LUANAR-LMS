export type LauncherBadge = {
  count?: number;
  label?: string;
  tone?: string;
} | null;

export type LauncherApp = {
  key: string;
  badge: LauncherBadge;
};

export type LauncherResponse = {
  apps: LauncherApp[];
};

export async function getLauncherApps(): Promise<LauncherResponse> {
  const res = await fetch("/api/apps/launcher/");
  if (!res.ok) {
    throw new Error("Failed to load launcher apps");
  }
  return res.json();
}
