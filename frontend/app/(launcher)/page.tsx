import { AppLauncherGrid } from "@/components/launcher/app-launcher-grid";

export default function LauncherPage() {
  return (
    <div className="mx-auto w-full max-w-6xl p-6">
      <div className="mb-6">
        <p className="text-text-secondary">Access your available apps</p>
      </div>
      <AppLauncherGrid />
    </div>
  );
}
