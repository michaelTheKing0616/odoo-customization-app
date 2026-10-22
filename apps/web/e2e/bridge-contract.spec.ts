import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function noSeriousAxe(page: Page, label: string) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .disableRules(["document-title", "html-has-lang"])
    .analyze();
  const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(serious, `${label}: ${JSON.stringify(serious, null, 2)}`).toEqual([]);
}

test.describe("Bridge Contract Studio UI-S-52 pass", () => {
  test("empty: studio chrome, one teal primary, quiet honesty, no amber", async ({ page }) => {
    await page.goto("/e2e/bridge-contract?state=empty");
    await expect(page.getByTestId("bridge-contract-page")).toBeVisible();
    await expect(page.getByTestId("bridge-honesty")).toHaveText("Read-only check. Nothing connects, sends, or syncs.");
    await expect(page.getByTestId("bridge-status-chip")).toHaveText("Draft");
    await expect(page.locator("button.bg-accent")).toHaveCount(1);
    await expect(page.getByTestId("bridge-validate-btn")).toHaveClass(/bg-accent/);
    await expect(page.getByTestId("bridge-risk")).toHaveCount(0);
    await expect(page.getByTestId("bridge-sheet")).toBeVisible();
    await expect(page.getByTestId("bridge-check-distinct")).toHaveAttribute("data-status", "wait");
    await noSeriousAxe(page, "empty");
  });

  test("invalid: per-field errors are instructions", async ({ page }) => {
    await page.goto("/e2e/bridge-contract?state=invalid");
    await expect(page.getByTestId("bridge-error-thirdId")).toContainText("Enter the third-party connection id.");
    await expect(page.getByTestId("bridge-error-conflict")).toContainText("Choose who wins");
    await expect(page.getByTestId("bridge-third-id")).toHaveAttribute("aria-invalid", "true");
    await expect(page.getByTestId("bridge-check-conflict")).toHaveAttribute("data-status", "fail");
    await noSeriousAxe(page, "invalid");
  });

  test("passed: ledger all green and nothing synced", async ({ page }) => {
    await page.goto("/e2e/bridge-contract?state=passed");
    await expect(page.getByTestId("bridge-result-passed-title")).toContainText("Tier I passed for two-way");
    await expect(page.getByTestId("bridge-result-passed-next")).toContainText("Nothing has synced");
    await expect(page.getByTestId("bridge-status-chip")).toHaveText("Tier I passed");
    await expect(page.getByTestId("bridge-tally")).toContainText("7/7");
    await noSeriousAxe(page, "passed");
  });

  test("refused: unverified connections named by side", async ({ page }) => {
    await page.goto("/e2e/bridge-contract?state=refused");
    await expect(page.getByTestId("bridge-result-refused-title")).toContainText("Connections are not verified");
    await expect(page.getByTestId("bridge-result-refused-why")).toContainText("Odoo connection odoo-main was not found");
    await expect(page.getByTestId("bridge-check-odoo_verified")).toHaveAttribute("data-status", "fail");
    await expect(page.getByTestId("bridge-check-third_verified")).toHaveAttribute("data-status", "fail");
    await noSeriousAxe(page, "refused");
  });

  test("error: network what/why/next keeps entries, retry is secondary", async ({ page }) => {
    await page.goto("/e2e/bridge-contract?state=error");
    await expect(page.getByTestId("bridge-result-error-title")).toContainText("Could not reach Tier I");
    await expect(page.getByTestId("bridge-result-error-why")).toContainText("HTTP 502");
    await expect(page.getByTestId("bridge-odoo-id")).toHaveValue("odoo-main");
    await expect(page.getByTestId("bridge-retry-btn")).not.toHaveClass(/bg-accent/);
  });

  test("risk: amber appears only for Remote wins overwrite", async ({ page }) => {
    await page.goto("/e2e/bridge-contract?state=risk");
    await expect(page.getByTestId("bridge-risk")).toContainText("overwrite Odoo order totals");
    await noSeriousAxe(page, "risk");
  });

  test("request tab shows the exact body and copy", async ({ page }) => {
    await page.goto("/e2e/bridge-contract?state=request");
    await expect(page.getByTestId("bridge-preview")).toContainText('"conflict_resolution": "manual"');
    await expect(page.getByTestId("bridge-copy-btn")).toBeVisible();
    await noSeriousAxe(page, "request");
  });

  test("live: canvas to inspector, keyboard flow to pass, then stale", async ({ page }) => {
    await page.goto("/e2e/bridge-contract?state=live");
    await page.getByTestId("bridge-node-odoo").click();
    await expect(page.getByTestId("bridge-odoo-id")).toBeFocused();
    await page.getByTestId("bridge-odoo-id").fill("verified-odoo");
    await page.getByTestId("bridge-third-id").fill("verified-shop");
    await expect(page.getByTestId("bridge-node-third")).toHaveText("verified-shop");
    await page.getByTestId("bridge-direction-two_way").check();
    await page.getByTestId("bridge-conflict-remote_wins").check();
    await expect(page.getByTestId("bridge-risk")).toBeVisible();
    await page.keyboard.press("ControlOrMeta+Enter");
    await expect(page.getByTestId("bridge-result-passed")).toBeVisible();
    await page.getByTestId("bridge-money").uncheck();
    await expect(page.getByTestId("bridge-result-stale")).toBeVisible();
    await expect(page.getByTestId("bridge-status-chip")).toHaveText("Edited since check");
  });

  test("live route keeps the Contract Studio heading", async ({ page }) => {
    await page.goto("/bridge/contracts/new");
    await expect(page.getByRole("heading", { name: "Contract Studio" })).toBeVisible();
    await expect(page.locator("button.bg-accent")).toHaveCount(1);
  });
});
