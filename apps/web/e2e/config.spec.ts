import { expect, test } from "@playwright/test";

test.describe("Instance Config UI-S-36", () => {
  test("honesty banner and idle what/why/next; Apply locked until dry-run", async ({
    page,
  }) => {
    await page.goto("/e2e/config?state=idle");
    await expect(page.getByTestId("config-page")).toBeVisible();
await expect(page.getByTestId("config-studio-chrome")).toBeVisible();
    await expect(page.getByTestId("config-studio-bar")).toBeVisible();
        await expect(page.getByTestId("config-honesty")).toBeVisible();
    await expect(page.getByTestId("config-honesty-title")).toContainText(
      /Test run never writes/i,
    );
    await expect(page.getByTestId("config-idle-guide")).toBeVisible();
    await expect(page.getByTestId("config-stage-rail")).toBeVisible();
    await expect(page.getByTestId("config-step-recipes")).toHaveAttribute(
      "data-state",
      "current",
    );
  });

  test("empty state shows what/why/next", async ({ page }) => {
    await page.goto("/e2e/config?state=empty");
    await expect(page.getByTestId("config-empty-guide")).toBeVisible();
    await expect(page.getByTestId("config-empty-guide-next")).toContainText(
      /Reload|Connect/i,
    );
    await expect(page.getByRole("button", { name: /Reload recipes/i })).toBeVisible();
  });

  test("configure keeps Apply locked with unlock reason", async ({ page }) => {
    await page.goto("/e2e/config?state=configure");
    await expect(page.getByTestId("day1-panel")).toBeVisible();
    await expect(page.getByTestId("config-apply-btn")).toBeDisabled();
    await expect(page.getByTestId("config-apply-btn")).toHaveClass(/bg-accent/);
    await expect(page.getByTestId("config-unlock-reason")).toContainText(/unlocks after/i);
    await expect(page.getByTestId("config-step-configure")).toHaveAttribute(
      "data-state",
      "current",
    );
  });

  test("dry-run result labels no writes and unlocks Apply", async ({ page }) => {
    await page.goto("/e2e/config?state=dry-run");
    await expect(page.getByTestId("config-apply-btn")).toBeEnabled();
    await expect(page.getByTestId("config-result-label")).toContainText(
      "Test run plan (no writes)",
    );
    await expect(page.getByTestId("recipe-plan-preview")).toHaveAttribute(
      "data-dry-run",
      "true",
    );
    await expect(page.getByTestId("config-step-dry-run")).toHaveAttribute(
      "data-state",
      "current",
    );
  });

  test("settings board primary is Save the setting", async ({ page }) => {
    await page.goto("/e2e/config?state=settings");
    await expect(page.getByTestId("config-save-setting-btn")).toBeVisible();
    await expect(page.getByTestId("config-save-setting-btn")).toHaveText(
      "Save the setting",
    );
    await expect(page.getByTestId("config-save-setting-btn")).toHaveClass(/bg-accent/);
    await expect(page.getByTestId("config-result-label")).toContainText("no writes");
  });

  test("applied result labels writes applied", async ({ page }) => {
    await page.goto("/e2e/config?state=applied");
    await expect(page.getByTestId("config-result-label")).toContainText(
      "Applied plan (writes applied)",
    );
    await expect(page.getByTestId("config-applied-guide")).toBeVisible();
    await expect(page.getByTestId("config-step-save")).toHaveAttribute(
      "data-state",
      "current",
    );
  });

  test("error state shows classified why and next", async ({ page }) => {
    await page.goto("/e2e/config?state=error");
    await expect(page.getByTestId("config-error-notice")).toBeVisible();
    await expect(page.getByTestId("config-error-why")).not.toHaveText("");
    await expect(page.getByTestId("config-error-next")).toBeVisible();
  });

  test("no em dashes in harness chrome copy", async ({ page }) => {
    await page.goto("/e2e/config?state=idle");
    const text = await page.getByTestId("config-page").innerText();
    expect(text).not.toMatch(/[—–]/);
  });
});
