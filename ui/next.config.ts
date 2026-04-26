import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Type-checking is run separately (tsc --noEmit in CI / VS Code language server).
  // next build's own TS pass trips on Zustand persist generic inference in Docker;
  // disabling it here avoids false-positive build failures.
  typescript: {
    ignoreBuildErrors: true,
  },
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
  async redirects() {
    return [
      {
        source: "/mempalace",
        destination: "/palace",
        permanent: true,
      },
    ];
  },
  // Backend proxying is handled by the API route at
  // src/app/api/backend/[...path]/route.ts which reads API_BASE_URL at runtime.
  // A next.config rewrite would bake the URL at build time, causing misrouting
  // in containerized deployments where the env var is set at runtime.
};

export default nextConfig;
