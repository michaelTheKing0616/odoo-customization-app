import { expect, test } from "@playwright/test";

test.describe("Operations hub UI-S-29", () => {
  test("masthead orientation + one teal primary; honesty as quiet caption", async ({ page }) => {
    await page.goto("/e2e/operations?state=idle");
    await expect(page.getByTestId("operations-hub")).toBeVisible();

    // Orientation is inline typography, not a twin Callout stack
    await expect(page.getByTestId("ops-hub-pick-guide")).toBeVisible();
    await expect(page.getByTestId("ops-hub-pick-guide-next")).toContainText(/Bulk Suite/i);
    await expect(page.locator(".ops-hub-operate .oh-guide")).toHaveCount(0);
    await expect(page.locator(".ops-hub-operate .oh-caption")).toHaveCount(1);

    await expect(page.getByTestId("ops-hub-honesty")).toBeVisible();
    await expect(page.getByTestId("ops-hub-honesty-title")).toContainText(/Ops tools can write/i);

    const cta = page.getByTestId("ops-hub-primary-cta");
    await expect(cta).toBeVisible();
    await expect(cta).toHaveClass(/bg-accent/);
    await expect(cta).toContainText(/Open Bulk Suite/i);
    await expect(cta).toHaveAttribute("href", /\/connections\/demo-conn\/bulk-suite$/);

    // Tool cards stay quiet links (no nested primary buttons)
    const primaries = page.locator('[data-testid="ops-hub-groups"] .bg-accent');
    await expect(primaries).toHaveCount(0);

    await expect(page.getByTestId("ops-hub-tool-bulk-suite")).toHaveAttribute("data-featured", "true");
    await expect(page.getByTestId("ops-hub-group-write")).toBeVisible();
    await expect(page.getByTestId("ops-hub-tool-script-runner")).toBeVisible();
  });

  test("no em dashes and no fake metrics on hub chrome", async ({ page }) => {
    await page.goto("/e2e/operations?state=idle");
    const text = await page.getByTestId("operations-hub").innerText();
    expect(text).not.toMatch(/[—–]/);
    expect(text.toLowerCase()).not.toMatch(/98\.7%|\d{3,} records today/);
  });

  test("every ops tool link stays on its own route", async ({ page }) => {
    await page.goto("/e2e/operations?state=idle");
    const expected = [
      "live-demo-copilot",
      "bulk-suite",
      "power-ops",
      "cron-manager",
      "housekeeping",
      "reminders",
      "script-runner",
    ];
    for (const id of expected) {
      const link = page.getByTestId(`ops-hub-tool-${id}`);
      await expect(link).toHaveAttribute("href", new RegExp(`/connections/demo-conn/${id}$`));
    }
  });
});
