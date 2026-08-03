import { expect, test } from "@playwright/test";

test.describe("Designer keyboard reorder", () => {
  test("arrow keys move selected canvas field", async ({ page }) => {
    await page.goto("/e2e/designer?mode=form");
    await expect(page.getByTestId("form-canvas")).toBeVisible();

    const firstField = page.getByRole("button", { name: /Name.*x_name/i });
    await firstField.click();

    const secondField = page.getByRole("button", { name: /Customer.*x_partner_id/i });
    await expect(firstField).toBeVisible();
    await expect(secondField).toBeVisible();

    await page.keyboard.press("ArrowDown");

    const rows = page.locator('[data-testid="form-canvas"] ul li');
    await expect(rows.nth(0)).toContainText("Customer");
    await expect(rows.nth(1)).toContainText("Name");

    await page.keyboard.press("ArrowUp");
    await expect(rows.nth(0)).toContainText("Name");
    await expect(rows.nth(1)).toContainText("Customer");
  });
});
