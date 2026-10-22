import { test, expect } from "@playwright/test";
import path from "node:path";

const OUT = path.resolve(__dirname, "../../../docs/vision-verify/DOC-WEBSITE");

test.describe("DOC-WEBSITE vision", () => {
  test("captures desktop / empty / locked / error", async ({ page }) => {
    await page.goto("/e2e/website");
    await expect(page.getByTestId("website-harness")).toBeVisible();

    await page.getByTestId("shot-desktop").click();
    await expect(page.getByTestId("website-paper-preview")).toBeVisible();
    await page.screenshot({
      path: path.join(OUT, "desktop.png"),
      fullPage: true,
    });

    await page.getByTestId("shot-empty").click();
    await expect(page.getByRole("heading", { name: "No website pages found" })).toBeVisible();
    await page.screenshot({
      path: path.join(OUT, "empty.png"),
      fullPage: true,
    });

    await page.getByTestId("shot-locked").click();
    await expect(page.getByTestId("website-paper-preview")).toBeVisible();
    await page.screenshot({
      path: path.join(OUT, "locked.png"),
      fullPage: true,
    });

    await page.getByTestId("shot-error").click();
    await page.getByTestId("website-save").click();
    await expect(page.getByTestId("website-error")).toBeVisible();
    await page.screenshot({
      path: path.join(OUT, "error.png"),
      fullPage: true,
    });
  });
});
