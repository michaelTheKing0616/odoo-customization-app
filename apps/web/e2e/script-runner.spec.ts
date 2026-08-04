import { expect, test } from "@playwright/test";

test.describe("Script Runner page", () => {
  test("renders editor and console", async ({ page }) => {
    await page.goto("/connect");
    const connectionLink = page.locator('a[href^="/connections/"]').first();
    if ((await connectionLink.count()) === 0) {
      test.skip();
    }
    const href = await connectionLink.getAttribute("href");
    if (!href) test.skip();
    await page.goto(`${href}/script-runner`);
    await expect(page.getByTestId("script-runner-page")).toBeVisible();
    await expect(page.getByTestId("script-runner-editor")).toBeVisible();
    await expect(page.getByTestId("script-runner-console")).toBeVisible();
  });
});
