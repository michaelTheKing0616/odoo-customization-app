import type { NextConfig } from "next";

/** Playwright runs `next build && next start`; standalone output breaks `next start`. */
const isPlaywrightE2eBuild = process.env.PLAYWRIGHT_E2E_BUILD === "1";
/**
 * Scripts assign INGENIUM_DIST_DIR themselves. Unset keeps Next's default `.next`
 * so `next dev` on port 3002 is unchanged. A remembered flag is not a distDir.
 */
const ingeniumDistDir = process.env.INGENIUM_DIST_DIR;
const distDir = ingeniumDistDir || (isPlaywrightE2eBuild ? ".next-e2e" : undefined);

const nextConfig: NextConfig = {
  ...(distDir ? { distDir } : {}),
  ...(isPlaywrightE2eBuild ? {} : { output: "standalone" }),
  // API proxy: apps/web/src/app/api/[...path]/route.ts (runtime API_PROXY_TARGET).
  async redirects() {
    return [
      // List hub currently lives on /connect (form + saved connections).
      {
        source: "/connections",
        destination: "/connect",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
