import { expect, test } from "@playwright/test";

test.describe("Automation gating callout (COPY_GUIDE three-options)", () => {
  test("renders title, why, options, and requires explicit choice", async ({ page }) => {
    await page.goto("/e2e/automation-gating");
    await expect(page.getByTestId("gating-callout")).toBeVisible();
    await expect(page.getByTestId("gating-title")).toContainText(
      "Automations aren't available",
    );
    await expect(page.getByTestId("gating-why")).toContainText("base_automation");
    await expect(page.getByTestId("gating-options").locator("li")).toHaveCount(3);
    await expect(page.getByTestId("gating-selected")).toHaveText("none");
    await page.getByTestId("gating-choice-leave_out").click();
    await expect(page.getByTestId("gating-selected")).toHaveText("leave_out");
  });
});
