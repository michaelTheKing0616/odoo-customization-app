import { expect, test } from "@playwright/test";

test.describe("Power Ops UI-S-31", () => {
  test("honesty banner and idle what/why/next; Run locked until dry-run", async ({ page }) => {
    await page.goto("/e2e/power-ops?state=idle");
    await expect(page.getByTestId("power-ops-page")).toBeVisible();
    await expect(page.getByTestId("power-ops-honesty")).toBeVisible();
    await expect(page.getByTestId("power-ops-honesty-title")).toContainText(/Test run never writes/i);
    await expect(page.getByTestId("power-ops-idle-guide")).toBeVisible();
    await expect(page.getByTestId("power-ops-stage-rail")).toBeVisible();
    await expect(page.getByTestId("power-ops-step-configure")).toHaveAttribute("data-state", "current");
    await expect(page.getByTestId("power-ops-run-btn")).toBeDisabled();
    await expect(page.getByTestId("power-ops-run-btn")).toHaveClass(/bg-accent/);
    await expect(page.getByTestId("power-ops-danger-zone")).toBeVisible();
  });

  test("empty state shows what/why/next and re-probe", async ({ page }) => {
    await page.goto("/e2e/power-ops?state=empty");
    await expect(page.getByTestId("power-ops-empty-guide")).toBeVisible();
    await expect(page.getByTestId("power-ops-empty-guide-next")).toContainText(/Re-probe|module/i);
    await expect(page.getByRole("button", { name: /Re-probe connection/i })).toBeVisible();
    await expect(page.getByTestId("power-ops-step-recipe")).toHaveAttribute("data-state", "current");
  });

  test("dry-run result labels no writes and unlocks Run recipe", async ({ page }) => {
    await page.goto("/e2e/power-ops?state=dry-run");
    await expect(page.getByTestId("power-ops-run-btn")).toBeEnabled();
    await expect(page.getByTestId("power-ops-result-label")).toContainText("Test run result (no writes)");
    await expect(page.getByTestId("power-ops-result-counts")).toHaveAttribute("data-dry-run", "true");
    await expect(page.getByTestId("power-ops-step-dry-run")).toHaveAttribute("data-state", "current");
    await expect(page.getByTestId("power-ops-partial-guide")).toBeVisible();
  });

  test("executed result labels writes applied", async ({ page }) => {
    await page.goto("/e2e/power-ops?state=executed");
    await expect(page.getByTestId("power-ops-result-label")).toContainText("Run result (writes applied)");
    await expect(page.getByTestId("power-ops-result-counts")).toHaveAttribute("data-dry-run", "false");
    await expect(page.getByTestId("power-ops-step-run")).toHaveAttribute("data-state", "current");
  });

  test("blocked recipe shows what/why/next", async ({ page }) => {
    await page.goto("/e2e/power-ops?state=blocked");
    await expect(page.getByTestId("power-ops-blocked-guide")).toBeVisible();
    await expect(page.getByTestId("power-ops-blocked-guide-why")).toContainText(/major/i);
  });

  test("error state shows classified why and next", async ({ page }) => {
    await page.goto("/e2e/power-ops?state=error");
    await expect(page.getByTestId("power-ops-error-notice")).toBeVisible();
    await expect(page.getByTestId("power-ops-error-why").textContent()).not.toBe("");
    await expect(page.getByTestId("power-ops-error-next")).toBeVisible();
  });

  test("no em dashes in harness chrome copy", async ({ page }) => {
    await page.goto("/e2e/power-ops?state=idle");
    const text = await page.getByTestId("power-ops-page").innerText();
    expect(text).not.toMatch(/[—–]/);
  });
});
