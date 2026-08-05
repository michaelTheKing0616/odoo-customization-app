import type { NextConfig } from "next";

/** Playwright runs `next build && next start`; standalone output breaks `next start`. */
const isPlaywrightE2eBuild = process.env.PLAYWRIGHT_E2E_BUILD === "1";

const nextConfig: NextConfig = {
  ...(isPlaywrightE2eBuild
    ? { distDir: ".next-e2e" }
    : { output: "standalone" }),
};

export default nextConfig;
