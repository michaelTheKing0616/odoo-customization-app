import { expect, test } from "@playwright/test";
import path from "node:path";

const OUT_DIR = path.resolve(__dirname, "../../../docs/vision-verify");

test.describe("Website editor UI loop", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/connections/e2e-connection/website/**", async (route) => {
      const url = route.request().url();
      const method = route.request().method();
      if (url.includes("/upload-image") && method === "POST") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            attachment_id: 99,
            src: "/web/image/99",
            name: "hero.png",
          }),
        });
        return;
      }
      if (url.includes("/publish") && method === "POST") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ ok: true, page_id: 1, is_published: false }),
        });
        return;
      }
      if (url.includes("/blocks") && method === "PUT") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ ok: true, view_id: 10, arch_len: 100 }),
        });
        return;
      }
      await route.continue();
    });
  });

  test("edit paragraph publish and save", async ({ page }) => {
    await page.goto("/e2e/website");
    await expect(page.getByTestId("website-harness")).toBeVisible();
    await expect(page.getByTestId("website-editor-panel")).toBeVisible();
    await page.getByTestId("block-text-p-1").fill("Edited copy");
    await page.getByTestId("website-publish-toggle").click();
    await expect(page.getByText("Page unpublished")).toBeVisible();
    await page.getByTestId("website-save").click();
    await expect(page.getByText("Page saved")).toBeVisible();
    await page.screenshot({
      path: path.join(OUT_DIR, "website-editor.png"),
      fullPage: true,
    });
  });

  test("reorder block within section", async ({ page }) => {
    await page.goto("/e2e/website");
    await page.getByTestId("reorder-down-p-1").click();
    await page.getByTestId("website-save").click();
    await expect(page.getByText("Page saved")).toBeVisible();
  });
});
