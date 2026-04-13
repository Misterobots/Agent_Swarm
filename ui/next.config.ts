import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async headers() {
    return [
      {
        // Prevent aggressive caching of HTML pages so deploys take effect immediately
        source: "/((?!_next/static|_next/image|favicon.ico).*)",
        headers: [
          {
            key: "Cache-Control",
            value: "no-cache, no-store, must-revalidate",
          },
        ],
      },
    ];
  },
  // Backend proxying is handled by the API route at
  // src/app/api/backend/[...path]/route.ts which reads API_BASE_URL at runtime.
  // A next.config rewrite would bake the URL at build time, causing misrouting
  // in containerized deployments where the env var is set at runtime.
};

export default nextConfig;
