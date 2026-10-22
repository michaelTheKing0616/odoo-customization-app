import { test, expect } from "@playwright/test";
import path from "node:path";

const OUT = path.resolve(__dirname, "../../../docs/vision-verify/DOC-MAIL");

test.describe("DOC-MAIL vision", () => {
  test("captures desktop / empty / preview", async ({ page }) => {
    await page.goto("/e2e/mail-templates");
    await expect(page.getByTestId("mail-templates-e2e")).toBeVisible();

    await page.getByTestId("shot-desktop").click();
    await page.screenshot({
      path: path.join(OUT, "desktop.png"),
      fullPage: true,
    });

    await page.getByTestId("shot-empty").click();
    await page.screenshot({
      path: path.join(OUT, "empty.png"),
      fullPage: true,
    });

    await page.getByTestId("shot-preview").click();
    await expect(page.getByTestId("mail-paper-preview")).toBeVisible();
    await page.screenshot({
      path: path.join(OUT, "preview.png"),
      fullPage: true,
    });
  });
});
