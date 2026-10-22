import { test, expect } from "@playwright/test";

/**
 * Q2 touch 142: on a repeat visit the app shell paints within 100 ms of the page arriving (no blank wait on the network),
 * and the production build logs no hydration error while the device cache fills the shell.
 */
const base = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3010";
const HYDRATION = /hydrat|Minified React error #(418|423|425)|did not match/i;

test("142: shell paints under 100 ms on a repeat visit, with no hydration error", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (m) => { if (m.type() === "error" && HYDRATION.test(m.text())) errors.push(m.text()); });
  page.on("pageerror", (e) => { if (HYDRATION.test(e.message)) errors.push(e.message); });
  await page.addInitScript(() => {
    const w = window as unknown as { __shellAt?: number };
    const seen = () => { if (w.__shellAt === undefined && document.querySelector('[data-testid="app-shell"],[data-testid="app-shell-loading"]')) w.__shellAt = performance.now(); };
    new MutationObserver(seen).observe(document, { childList: true, subtree: true });
    document.addEventListener("DOMContentLoaded", seen);
  });
  const CONN = { id: "c1", name: "Main DB", url: "https://main.odoo.com", db_name: "main", username: "a@b.c", server_version: "18.0", is_test_copy: false };
  await page.route("**/api/**", (r) => {
    const u = new URL(r.request().url()).pathname;
    if (u === "/api/connections") return r.fulfill({ json: [CONN] });
    if (u === "/api/connections/c1") return r.fulfill({ json: CONN });
    return r.fulfill({ json: [] });
  });
  await page.goto(`${base}/connections/c1`);
  await page.getByTestId("app-shell").or(page.getByTestId("app-shell-loading")).first().waitFor();
  await page.waitForLoadState("networkidle");
  // Repeat visit: the device cache is warm now.
  await page.reload();
  await page.getByTestId("app-shell").or(page.getByTestId("app-shell-loading")).first().waitFor();
  const ms = await page.evaluate(() => {
    const w = window as unknown as { __shellAt?: number };
    const nav = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming;
    return (w.__shellAt ?? Infinity) - nav.responseEnd;
  });
  await page.waitForLoadState("networkidle");
  expect(ms, `shell painted ${ms.toFixed(1)} ms after the page arrived`).toBeLessThan(100);
  expect(errors).toEqual([]);
});
