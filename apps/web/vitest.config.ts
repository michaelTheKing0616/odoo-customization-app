import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  esbuild: {
    jsx: "automatic",
  },
  // Tests never need Tailwind: an inline empty PostCSS config stops Vite loading the app's
  // string-form plugin list (which it rejects) when a page imports a plain .css file.
  css: { postcss: { plugins: [] } },
  test: {
    environment: "happy-dom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["./vitest.setup.ts"],
    css: false,
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
    alias: [
      {
        find: /^(.+)\.module\.css$/,
        replacement: path.resolve(__dirname, "./vitest.css-module-stub.js"),
      },
      {
        find: "@",
        replacement: path.resolve(__dirname, "./src"),
      },
    ],
  },
});
