import type { NextConfig } from "next";

/** Playwright runs `next build && next start`; standalone output breaks `next start`. */
const isPlaywrightE2eBuild = process.env.PLAYWRIGHT_E2E_BUILD === "1";

const apiProxyTarget = (process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8001").replace(
  /\/$/,
  "",
);

const nextConfig: NextConfig = {
  ...(isPlaywrightE2eBuild
    ? { distDir: ".next-e2e" }
    : { output: "standalone" }),
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiProxyTarget}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
