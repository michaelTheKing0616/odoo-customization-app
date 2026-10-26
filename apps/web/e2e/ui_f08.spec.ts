/** Locked oracle for UI-F08. Worker must not edit this file. */
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test.describe("UI-F08", () => {
  test("axe reports no serious or critical issues on the harness", async ({ page }) => {
    await page.goto("/e2e/ui-f08");
    await expect(page.getByTestId("ui-f08-harness")).toBeVisible();
    const results = await new AxeBuilder({ page })
      .include('[data-testid="ui-f08-harness"]')
      .analyze();
    const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(bad).toEqual([]);
  });

  test("error toast stays visible after 10s", async ({ page }) => {
    await page.goto("/e2e/ui-f08");
    await page.getByRole("button", { name: "Show error" }).click();
    const toast = page.getByRole("listitem").filter({ hasText: "Something went wrong" }).first();
    await expect(toast).toBeVisible();
    await page.waitForTimeout(10_000);
    await expect(toast).toBeVisible();
  });
});
