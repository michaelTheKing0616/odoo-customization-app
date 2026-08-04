import { expect, test } from "@playwright/test";

test.describe("Code Studio page", () => {
  test("renders editor when gate allows or shows gating callout", async ({ page }) => {
    await page.goto("/connect");
    const firstLink = page.locator('[data-testid^="nav-"]').first();
    if ((await firstLink.count()) === 0) {
      test.skip();
    }
    const connectionLink = page.locator('a[href^="/connections/"]').first();
    if ((await connectionLink.count()) === 0) {
      test.skip();
    }
    const href = await connectionLink.getAttribute("href");
    if (!href) test.skip();
    await page.goto(`${href}/code-studio`);
    await expect(page.getByTestId("code-studio-page")).toBeVisible();
    const editor = page.getByTestId("code-studio-editor");
    const gating = page.getByTestId("gating-callout");
    await expect(editor.or(gating)).toBeVisible();
  });
});
