import { expect, test } from "@playwright/test";

test.describe("Fleet command UI-S-51", () => {
  test("masthead CTA + quiet honesty; no twin Callout stack on idle", async ({ page }) => {
    await page.goto("/e2e/command?state=idle");
    await expect(page.getByTestId("command-center-page")).toBeVisible();
    await expect(page.getByTestId("fleet-honesty")).toBeVisible();
    await expect(page.getByTestId("fleet-honesty-title")).toContainText(/Counts span the whole fleet/i);
    await expect(page.getByTestId("fleet-idle-guide")).toBeVisible();

    // Idle: orientation in masthead; honesty is caption; no stacked Why/Next Callouts
    await expect(page.locator(".fleet-operate .fc-guide")).toHaveCount(0);
    await expect(page.locator(".fleet-operate .fc-caption")).toHaveCount(1);

    const cta = page.getByTestId("fleet-primary-cta");
    await expect(cta).toBeVisible();
    await expect(cta).toHaveClass(/bg-accent/);
    await expect(cta).toContainText(/Open a client/i);
    await expect(cta).toHaveAttribute("href", "/connect");

    await expect(page.getByTestId("command-tile-clients-count")).toHaveText("3");
    await expect(page.getByTestId("fleet-stage-rail")).toBeVisible();
    await expect(page.getByTestId("fleet-step-inspect")).toHaveAttribute("data-state", "current");
  });

  test("empty fleet uses Connect Odoo as sole primary", async ({ page }) => {
    await page.goto("/e2e/command?state=empty");
    await expect(page.getByTestId("fleet-empty-guide")).toBeVisible();
    const cta = page.getByTestId("fleet-primary-cta");
    await expect(cta).toContainText(/Connect Odoo/i);
    await expect(cta).toHaveClass(/bg-accent/);
    await expect(page.getByTestId("command-tile-clients-count")).toContainText("0");
  });

  test("partial keeps sibling counts and shows retry honesty", async ({ page }) => {
    await page.goto("/e2e/command?state=partial");
    await expect(page.getByTestId("fleet-partial-guide")).toBeVisible();
    await expect(page.getByTestId("command-tile-clients-count")).toHaveText("3");
    await expect(page.getByTestId("command-tile-drift-count")).toHaveText("1");
    await expect(page.getByTestId("command-tile-failed-jobs")).toHaveAttribute("data-phase", "error");
  });

  test("no em dashes on fleet chrome", async ({ page }) => {
    await page.goto("/e2e/command?state=idle");
    const text = await page.getByTestId("command-center-page").innerText();
    expect(text).not.toMatch(/[\u2014\u2013]/);
  });
});
