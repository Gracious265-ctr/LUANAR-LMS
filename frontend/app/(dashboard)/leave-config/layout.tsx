import type { Metadata } from "next";

/**
 * The whole module sits under one layout so its three routes — list, create,
 * edit — share a title instead of each restating it. The rail itself is not
 * laid out here: `DashboardShell` already renders `LEAVE_CONFIG_NAV_ITEMS`
 * for any path under `/leave-config`, so a nested layout would only duplicate
 * what the shell decides from the pathname.
 */
export const metadata: Metadata = {
  title: "Leave Configuration",
  description:
    "The leave types that Leave, Plans and Approvals all read from.",
};

export default function LeaveConfigLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
