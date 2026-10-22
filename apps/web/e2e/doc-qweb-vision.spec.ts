import { test, expect } from "@playwright/test";
import path from "node:path";

const OUT = path.resolve(__dirname, "../../../docs/vision-verify/DOC-QWEB");

test.describe("DOC-QWEB vision", () => {
  test("captures desktop / empty / source / error", async ({ page }) => {
    await page.goto("/e2e/qweb-views");
    await expect(page.getByTestId("qweb-views-e2e")).toBeVisible();

    await page.getByTestId("shot-desktop").click();
    await expect(page.getByTestId("qweb-views-workbench")).toBeVisible();
    await page.screenshot({
      path: path.join(OUT, "desktop.png"),
      fullPage: true,
    });

    await page.getByTestId("shot-empty").click();
    await expect(page.getByTestId("qweb-views-workbench")).toBeVisible();
    await page.screenshot({
      path: path.join(OUT, "empty.png"),
      fullPage: true,
    });

    await page.getByTestId("shot-source").click();
    await expect(page.getByTestId("qweb-source-xml")).toBeVisible();
    await page.screenshot({
      path: path.join(OUT, "source.png"),
      fullPage: true,
    });

    await page.getByTestId("shot-error").click();
    await expect(page.getByTestId("qweb-error")).toBeVisible();
    await expect(page.getByTestId("qweb-error-what")).toBeVisible();
    await page.screenshot({
      path: path.join(OUT, "error.png"),
      fullPage: true,
    });
  });
});
