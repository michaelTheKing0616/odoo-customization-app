import { expect, test } from "@playwright/test";

test.describe("Change journal UI-S-38", () => {
  test("honesty banner and idle what/why/next; teal Roll back", async ({ page }) => {
    await page.goto("/e2e/journal?state=idle");
    await expect(page.getByTestId("journal-page")).toBeVisible();
await expect(page.getByTestId("journal-studio-chrome")).toBeVisible();
    await expect(page.getByTestId("journal-studio-bar")).toBeVisible();
        await expect(page.getByTestId("journal-honesty")).toBeVisible();
    await expect(page.getByTestId("journal-honesty-title")).toContainText(/partial|Audit is replay/i);
    await expect(page.getByTestId("journal-idle-guide")).toBeVisible();
    await expect(page.getByTestId("journal-stage-rail")).toBeVisible();
    await expect(page.getByTestId("journal-step-timeline")).toHaveAttribute("data-state", "current");
    await expect(page.getByTestId("journal-chain-note")).toContainText(/T5A-03/);
    const rollback = page.getByTestId("journal-rollback-btn");
    await expect(rollback).toBeEnabled();
    await expect(rollback).toHaveClass(/bg-accent/);
    await expect(rollback).toHaveText("Roll back");
  });

  test("empty state shows what/why/next and refresh", async ({ page }) => {
    await page.goto("/e2e/journal?state=empty");
    await expect(page.getByTestId("journal-empty-guide")).toBeVisible();
    await expect(page.getByTestId("journal-empty-guide-next")).toContainText(/Refresh|snapshot/i);
    await expect(page.getByRole("button", { name: /Refresh timeline/i })).toBeVisible();
    await expect(page.getByTestId("journal-step-timeline")).toHaveAttribute("data-state", "current");
  });

  test("partial rollback honesty", async ({ page }) => {
    await page.goto("/e2e/journal?state=partial");
    await expect(page.getByTestId("journal-partial-guide")).toBeVisible();
    await expect(page.getByTestId("journal-partial-guide-why")).toContainText(/Dropped columns/i);
    await expect(page.getByTestId("journal-step-inspect")).toHaveAttribute("data-state", "current");
  });

  test("irreversible disables Roll back", async ({ page }) => {
    await page.goto("/e2e/journal?state=irreversible");
    await expect(page.getByTestId("journal-irreversible-guide")).toBeVisible();
    await expect(page.getByTestId("journal-rollback-irreversible")).toBeDisabled();
  });

  test("audit replay honesty", async ({ page }) => {
    await page.goto("/e2e/journal?state=audit");
    await expect(page.getByTestId("journal-audit-guide")).toBeVisible();
    await expect(page.getByTestId("journal-audit-guide-why")).toContainText(/does not undo/i);
  });

  test("health sweep guide", async ({ page }) => {
    await page.goto("/e2e/journal?state=health");
    await expect(page.getByTestId("journal-health-guide")).toBeVisible();
    await expect(page.getByTestId("journal-health-guide-title")).toContainText(/broken/i);
  });

  test("restored success guide advances stage", async ({ page }) => {
    await page.goto("/e2e/journal?state=restored");
    await expect(page.getByTestId("journal-rollback-success")).toBeVisible();
    await expect(page.getByTestId("journal-step-roll-back")).toHaveAttribute("data-state", "current");
  });

  test("error state shows classified why and next", async ({ page }) => {
    await page.goto("/e2e/journal?state=error");
    await expect(page.getByTestId("journal-error-notice")).toBeVisible();
    await expect(page.getByTestId("journal-error-why").textContent()).not.toBe("");
    await expect(page.getByTestId("journal-error-next")).toBeVisible();
  });

  test("no em dashes in harness chrome copy", async ({ page }) => {
    await page.goto("/e2e/journal?state=idle");
    const text = await page.getByTestId("journal-page").innerText();
    expect(text).not.toMatch(/[—–]/);
  });
});
