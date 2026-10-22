import { expect, test } from "@playwright/test";

test.describe("Live Demo Co-Pilot", () => {
  test("harness: honesty, stage rail, teal Launch primary", async ({ page }) => {
    await page.goto("/e2e/live-demo-copilot?state=empty");
    await expect(page.getByTestId("live-demo-copilot-page")).toBeVisible();
await expect(page.getByTestId("live-demo-studio-chrome")).toBeVisible();
    await expect(page.getByTestId("live-demo-studio-bar")).toBeVisible();
        await expect(page.getByTestId("live-demo-honesty")).toContainText(/Consent first|Mock|live/i);
    await expect(page.getByTestId("live-demo-step-meeting")).toBeVisible();
    await expect(page.getByTestId("live-demo-step-consent")).toBeVisible();
    await expect(page.getByTestId("live-demo-step-launch")).toBeVisible();
    await expect(page.getByTestId("live-demo-step-live")).toBeVisible();
    await expect(page.getByTestId("live-demo-launch-btn")).toBeVisible();
    await expect(page.getByTestId("live-demo-launch-btn")).toBeDisabled();
    await expect(page.getByTestId("live-demo-launch-btn")).toHaveText("Launch bot");
    await expect(page.getByTestId("live-demo-state-guide")).toContainText(/No session yet/i);
  });

  test("harness: ready enables Launch; consent step done", async ({ page }) => {
    await page.goto("/e2e/live-demo-copilot?state=ready");
    await expect(page.getByTestId("live-demo-step-launch")).toHaveAttribute("data-state", "current");
    await expect(page.getByTestId("live-demo-launch-btn")).toBeEnabled();
    await expect(page.getByTestId("live-demo-honesty")).toContainText(/Live Attendee|visible bot/i);
    await expect(page.getByTestId("open-presenter-overlay")).toBeEnabled();
  });

  test("harness: mock honesty and answers empty what/why/next", async ({ page }) => {
    await page.goto("/e2e/live-demo-copilot?state=mock");
    await expect(page.getByTestId("live-demo-honesty")).toContainText(/Mock mode/i);
    await expect(page.getByTestId("live-demo-mode-badge")).toContainText(/Mock/i);
    await expect(page.getByTestId("live-demo-answers-empty")).toContainText(/Inject|mock/i);
  });

  test("harness: declined and waiting what/why/next", async ({ page }) => {
    await page.goto("/e2e/live-demo-copilot?state=declined");
    await expect(page.getByTestId("live-demo-state-guide")).toContainText(/declined/i);
    await page.goto("/e2e/live-demo-copilot?state=waiting");
    await expect(page.getByTestId("live-demo-state-guide")).toContainText(/Host action/i);
  });

  test("harness: answers card and error notice", async ({ page }) => {
    await page.goto("/e2e/live-demo-copilot?state=answers");
    await expect(page.getByTestId("live-demo-answer-card")).toContainText(/multi-company/i);
    await page.goto("/e2e/live-demo-copilot?state=error");
    await expect(page.getByTestId("live-demo-error-notice")).toBeVisible();
    await expect(page.getByTestId("live-demo-error-next")).toContainText(/Diagnose|Refresh/i);
  });
});
