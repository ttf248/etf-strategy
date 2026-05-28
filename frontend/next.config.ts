import type { NextConfig } from "next";

const defaultApiOrigin = "http://127.0.0.1:8000";
const rawApiOrigin =
  process.env.STRATEGY_STUDIO_API_ORIGIN ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  defaultApiOrigin;
const apiOrigin = rawApiOrigin.replace(/\/+$/, "");

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiOrigin}/api/:path*`,
      },
      {
        source: "/health",
        destination: `${apiOrigin}/health`,
      },
    ];
  },
};

export default nextConfig;
