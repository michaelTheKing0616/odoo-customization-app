import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  esbuild: {
    jsx: "automatic",
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["./vitest.setup.ts"],
    environmentMatchGlobs: [
      ["src/lib/api.test.ts", "node"],
      ["src/lib/odoo-urls.test.ts", "node"],
      ["src/lib/jobs.test.ts", "node"],
      ["src/lib/capabilities.test.ts", "node"],
      ["src/components/scanner/scanUtils.test.ts", "node"],
      ["src/components/builders.test.ts", "node"],
      ["src/components/ui/Button.test.ts", "node"],
    ],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
