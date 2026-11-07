import type { NextConfig } from "next";

/**
 * Response headers that apply to every route.
 *
 * `nosniff` stops a browser from reinterpreting a JSON or upload response as
 * HTML/script; `DENY` keeps the app out of a frame, which also closes click-
 * jacking against the sign-in form; the referrer policy keeps employee ids and
 * application paths out of third-party `Referer` headers; and the permissions
 * policy turns off hardware APIs a leave form never needs. HSTS is deliberately
 * left to the TLS terminator (or Django's production settings), because a
 * header served over plain HTTP in local development is ignored and easy to
 * misread as protection.
 */
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), payment=()",
  },
];

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
