import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      // The leave module moved from `/dashboard/leave` and `/applications/[id]`
      // to `/leave/...`. Keep old bookmarks and any straggling links working.
      {
        source: "/dashboard/leave/:path*",
        destination: "/leave/:path*",
        permanent: false,
      },
      {
        source: "/applications/:id",
        destination: "/leave/applications/:id",
        permanent: false,
      },
      // The approvals module (and its approver-only cover pages) live under
      // `/approvals` now.
      {
        source: "/dashboard/approvals/:path*",
        destination: "/approvals/:path*",
        permanent: false,
      },
      {
        source: "/dashboard/cover/:path*",
        destination: "/approvals/cover/:path*",
        permanent: false,
      },
      // Organisation structure (teams, campuses, approver roles, role
      // assignments) moved under `/organisation`.
      {
        source: "/dashboard/hr-admin/teams/:path*",
        destination: "/organisation/teams/:path*",
        permanent: false,
      },
      {
        source: "/dashboard/hr-admin/campuses/:path*",
        destination: "/organisation/campuses/:path*",
        permanent: false,
      },
      {
        source: "/dashboard/hr-admin/roles/:path*",
        destination: "/organisation/roles/:path*",
        permanent: false,
      },
      {
        source: "/dashboard/hr-admin/approvers/:path*",
        destination: "/organisation/approvers/:path*",
        permanent: false,
      },
      // The rest of HR administration (employees, leave config, calendar,
      // delegations, reassignments, plans, audit, document template) moved
      // under `/hr-admin`. Listed after the organisation-specific rules so
      // those more specific paths win.
      {
        source: "/dashboard/hr-admin/:path*",
        destination: "/hr-admin/:path*",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
