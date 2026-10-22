import { expect, test } from "@playwright/test";

test.describe("API settings UI-S-41", () => {
  test("honesty banner and idle what/why/next; Create API key is teal primary", async ({
    page,
  }) => {
    await page.goto("/e2e/settings?state=idle");
    await expect(page.getByTestId("settings-page")).toBeVisible();
    await expect(page.getByTestId("settings-studio-chrome")).toBeVisible();
    await expect(page.getByTestId("settings-studio-bar")).toBeVisible();
    await expect(page.getByTestId("settings-honesty")).toBeVisible();
    await expect(page.getByTestId("settings-honesty-title")).toContainText(
      /shown once|this device/i,
    );
    await expect(page.getByTestId("settings-idle-guide")).toBeVisible();
    await expect(page.getByTestId("settings-stage-rail")).toBeVisible();
    await expect(page.getByTestId("settings-step-status")).toHaveAttribute(
      "data-state",
      "current",
    );
    await expect(page.getByTestId("settings-create-key-btn")).toHaveText("Create API key");
    await expect(page.getByTestId("settings-create-key-btn")).toHaveClass(/bg-accent/);
    await expect(page.getByTestId("settings-save-browser-btn")).toHaveClass(/bg-surface-raised|border/);
  });

  test("empty state shows what/why/next", async ({ page }) => {
    await page.goto("/e2e/settings?state=empty");
    await expect(page.getByTestId("settings-empty-guide")).toBeVisible();
    await expect(page.getByTestId("settings-empty-guide-next")).toContainText(
      /Create API key|Copy/i,
    );
    await expect(page.getByRole("heading", { name: "No API keys yet" })).toBeVisible();
  });

  test("bootstrap shows Generate first API key primary", async ({ page }) => {
    await page.goto("/e2e/settings?state=bootstrap");
    await expect(page.getByTestId("settings-bootstrap-btn")).toBeVisible();
    await expect(page.getByTestId("settings-bootstrap-btn")).toHaveText(
      "Generate first API key",
    );
    await expect(page.getByTestId("settings-bootstrap-btn")).toHaveClass(/bg-accent/);
    await expect(page.getByTestId("settings-bootstrap-guide")).toBeVisible();
    await expect(page.getByTestId("settings-create-key-btn")).toHaveCount(0);
  });

  test("revealed state shows copy once honesty", async ({ page }) => {
    await page.goto("/e2e/settings?state=revealed");
    await expect(page.getByTestId("settings-revealed-guide")).toBeVisible();
    await expect(page.getByTestId("settings-reveal-panel")).toBeVisible();
    await expect(page.getByTestId("settings-copy-key-btn")).toBeVisible();
    await expect(page.getByTestId("settings-step-keys")).toHaveAttribute(
      "data-state",
      "current",
    );
  });

  test("saved state shows browser save honesty guide", async ({ page }) => {
    await page.goto("/e2e/settings?state=saved");
    await expect(page.getByTestId("settings-saved-guide")).toBeVisible();
    await expect(page.getByTestId("settings-saved-guide-title")).toContainText(
      /saved in this browser/i,
    );
  });

  test("error state shows classified why and next", async ({ page }) => {
    await page.goto("/e2e/settings?state=error");
    await expect(page.getByTestId("settings-error-notice")).toBeVisible();
    await expect(page.getByTestId("settings-error-why")).not.toHaveText("");
    await expect(page.getByTestId("settings-error-next")).toBeVisible();
  });

  test("no em dashes in harness chrome copy", async ({ page }) => {
    await page.goto("/e2e/settings?state=idle");
    const text = await page.getByTestId("settings-page").innerText();
    expect(text).not.toMatch(/[—–]/);
  });
});
