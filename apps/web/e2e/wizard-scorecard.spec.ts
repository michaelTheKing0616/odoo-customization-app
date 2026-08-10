import { expect, test } from "@playwright/test";

const CONN = "test-conn";
const PROMPT = "A large mega super market with multiple branches";

const LOW_SCORE_DRAFT = {
  technical_name: "retail_supermarket",
  display_name: "Retail Supermarket",
  models: [{ model: "x_branch", description: "Branch", fields: [{ name: "x_name", ttype: "char" }] }],
  _llm_status: { mode: "llm_full" },
  _scorecard: {
    score_0_10: 7.2,
    dimensions: { domain_fit: 7, structure: 8, semantics: 8, ux: 7, hygiene: 7 },
    findings: [{ dimension: "structure", element: "x_branch", detail: "missing search view" }],
  },
};

const FIXED_DRAFT = {
  ...LOW_SCORE_DRAFT,
  _scorecard: {
    score_0_10: 9.4,
    dimensions: { domain_fit: 9.5, structure: 9.5, semantics: 9.5, ux: 9, hygiene: 9.5 },
    findings: [],
  },
};

test.describe("Wizard scorecard + expert review", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/connections/**", async (route) => {
      const url = route.request().url();
      if (url.match(/\/api\/connections\/[^/]+$/) && route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: CONN,
            name: "Test Connection",
            url: "http://127.0.0.1:8069",
            db_name: "odoo",
            username: "admin",
            server_version: "19.0",
            created_at: null,
            updated_at: null,
          }),
        });
        return;
      }
      if (url.includes("/reuse-catalog") && route.request().method() === "GET") {
        await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
        return;
      }
      await route.continue();
    });

    await page.route("**/api/apps/templates", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    });

    await page.route("**/api/ai/status", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ enabled: true, ollama_reachable: true }),
      });
    });

    await page.route("**/api/ai/component-gallery", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    });

    await page.route("**/api/ai/draft-cache**", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    });

    await page.route("**/api/ai/draft-module", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: true,
          draft: LOW_SCORE_DRAFT,
          warnings: [],
          note: "Draft only — does not apply.",
        }),
      });
    });

    await page.route("**/api/expert/review-draft", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          score_before: 7.2,
          score_after: 9.4,
          verdict: "ready",
          review_markdown: "**Draft quality: 7.2/10**\n\nAfter deterministic fixes: **9.4/10**",
          findings: [],
          repairs: ["post_critique: added search view"],
          suggestions: [],
          draft: FIXED_DRAFT,
        }),
      });
    });
  });

  test("shows scorecard chip and expert review improves score", async ({ page }) => {
    await page.goto(`/connections/${CONN}/wizard`);
    await expect(page.getByTestId("draft-studio")).toBeVisible();

    await page.getByPlaceholder(/Car rental fleet/i).fill(PROMPT);
    const draftBtn = page.getByTestId("create-draft");
    await expect(draftBtn).toBeEnabled();
    await draftBtn.click();

    await expect(page.getByTestId("draft-model-review")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("draft-scorecard-chip")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("Draft quality: 7.2/10")).toBeVisible();
    await expect(page.getByText(/Semantics 8\.0/)).toBeVisible();
    await expect(page.getByTestId("expert-review-fix")).toBeVisible();

    await page.getByTestId("expert-review-fix").click();
    await expect(page.getByText(/7\.2\/10 → 9\.4\/10/)).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Draft quality: 9.4/10 ✓")).toBeVisible();
  });
});
