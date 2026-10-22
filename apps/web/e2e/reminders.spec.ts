import { expect, test } from "@playwright/test";

test.describe("Reminders UI-S-34", () => {
  test("studio bar honesty and empty brief (no twin banner)", async ({ page }) => {
    await page.goto("/e2e/reminders?state=empty");
    await expect(page.getByTestId("reminders-page")).toBeVisible();
    await expect(page.getByTestId("reminders-studio-chrome")).toBeVisible();
    await expect(page.getByTestId("reminders-studio-bar")).toBeVisible();
    await expect(page.getByTestId("reminders-honesty")).toBeVisible();
    await expect(page.getByTestId("reminders-honesty-title")).toContainText(
      "Schedule will be enabled",
    );
    // Honesty lives in studio bar, not as a second stacked guide card
    await expect(page.locator(".rm-studio .rm-guide")).toHaveCount(0);
    await expect(page.getByTestId("reminders-step-rail")).toBeVisible();
    await expect(page.getByTestId("reminders-step-compose")).toHaveAttribute(
      "data-state",
      "current",
    );
    await expect(page.getByTestId("reminders-empty-guide")).toBeVisible();
    await expect(page.getByTestId("reminders-empty-guide-why")).toBeVisible();
    await expect(page.getByTestId("reminders-empty-guide-next")).toBeVisible();
    await expect(page.getByTestId("reminders-create-btn")).toHaveClass(/bg-accent/);
    await expect(page.getByTestId("reminders-schedule-headline")).toContainText(
      "Schedule enabled",
    );
  });

  test("template-only honesty when cron off", async ({ page }) => {
    await page.goto("/e2e/reminders?state=template-only");
    await expect(page.getByTestId("reminders-step-schedule")).toHaveAttribute(
      "data-state",
      "current",
    );
    await expect(page.getByTestId("reminders-honesty-title")).toContainText(
      "Template only",
    );
    await expect(page.getByTestId("reminders-schedule-preview")).toHaveAttribute(
      "data-enabled",
      "false",
    );
    await expect(page.getByTestId("reminders-schedule-headline")).toContainText(
      "Schedule off",
    );
    await expect(page.getByTestId("reminders-create-cron")).not.toBeChecked();
  });

  test("created with schedule shows cron id", async ({ page }) => {
    await page.goto("/e2e/reminders?state=created");
    await expect(page.getByTestId("reminders-step-created")).toHaveAttribute(
      "data-state",
      "current",
    );
    await expect(page.getByTestId("reminders-result")).toHaveAttribute(
      "data-scheduled",
      "true",
    );
    await expect(page.getByTestId("reminders-created-guide-title")).toContainText(
      "schedule enabled",
    );
    await expect(page.getByTestId("reminders-cron-id")).toContainText("91");
    await expect(page.getByTestId("reminders-template-id")).toContainText("44");
  });

  test("created-template stays schedule off", async ({ page }) => {
    await page.goto("/e2e/reminders?state=created-template");
    await expect(page.getByTestId("reminders-result")).toHaveAttribute(
      "data-scheduled",
      "false",
    );
    await expect(page.getByTestId("reminders-created-guide-title")).toContainText(
      "stayed off",
    );
    await expect(page.getByTestId("reminders-cron-id")).toContainText("none");
  });

  test("error guide is what/why/next", async ({ page }) => {
    await page.goto("/e2e/reminders?state=error");
    await expect(page.getByTestId("reminders-error-guide")).toBeVisible();
    await expect(page.getByTestId("reminders-error-guide-title")).toContainText(
      "Could not create",
    );
    await expect(page.getByTestId("reminders-error-guide-why")).toBeVisible();
    await expect(page.getByTestId("reminders-error-guide-next")).toBeVisible();
  });
});
