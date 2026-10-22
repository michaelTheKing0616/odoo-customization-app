import { test, expect } from "@playwright/test";

/** Sidebar connection switcher: saved connections (name, Live/Test, version), All connections, Add connection; keyboard and Cmd-K. */
const base = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3010";
const A = { id: "c1", name: "Main DB", url: "https://main.odoo.com", db_name: "main", username: "a", server_version: "18.0", is_test_copy: false };
const B = { id: "c2", name: "Staging", url: "https://stg.odoo.com", db_name: "main_test", username: "a", server_version: "19.0", is_test_copy: true };

test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", (r) => {
    const u = new URL(r.request().url()).pathname;
    if (u === "/api/connections") return r.fulfill({ json: [A, B] });
    if (u === "/api/connections/c1") return r.fulfill({ json: A });
    if (u === "/api/connections/c2") return r.fulfill({ json: B });
    return r.fulfill({ json: [] });
  });
});

test("switcher lists connections and works from the keyboard", async ({ page }) => {
  await page.goto(`${base}/connections/c1`);
  const btn = page.getByTestId("sidebar-switcher").filter({ visible: true });
  await btn.focus();
  await page.keyboard.press("ArrowDown");
  const menu = page.getByTestId("sidebar-switcher-menu").first().filter({ visible: true });
  await expect(menu).toBeVisible();
  await expect(page.getByTestId("sidebar-switcher-c1").filter({ visible: true })).toContainText("Live · Odoo 18");
  await expect(page.getByTestId("sidebar-switcher-c2").filter({ visible: true })).toContainText("Test · Odoo 19");
  await expect(page.getByTestId("sidebar-switcher-all").filter({ visible: true })).toBeVisible();
  await expect(page.getByTestId("sidebar-switcher-add").filter({ visible: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(menu).toBeHidden();
  await expect(btn).toBeFocused();
  await btn.press("Enter");
  await page.keyboard.press("ArrowDown"); // from current (Main DB) to Staging
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/connections\/c2/);
});

test("Add connection opens the Connect form, ready to type", async ({ page }) => {
  await page.goto(`${base}/connections/c1`);
  await page.getByTestId("sidebar-switcher").filter({ visible: true }).click();
  await page.getByTestId("sidebar-switcher-add").filter({ visible: true }).click();
  await expect(page).toHaveURL(/\/connect#new/);
  const label = page.getByLabel("Label", { exact: true });
  await label.fill("Third DB");
  await expect(label).toHaveValue("Third DB");
});

test("Cmd-K offers the connections", async ({ page }) => {
  await page.goto(`${base}/connections/c1`);
  await page.getByTestId("sidebar-switcher").filter({ visible: true }).waitFor();
  await page.keyboard.press("ControlOrMeta+k");
  await page.keyboard.type("Switch to Staging");
  await expect(page.getByText("Switch to Staging").first()).toBeVisible();
});
