import { expect, test } from "@playwright/test";
import path from "node:path";

const OUT_DIR = path.resolve(__dirname, "../../../docs/vision-verify");

test.describe("Expert UX flows (REM-9)", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/expert/ask", async (route) => {
      const body = route.request().postDataJSON() as { question?: string };
      const q = body.question ?? "";
      const isError = q.includes("Error log:") || q.toLowerCase().includes("diagnose");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          answer_markdown: isError
            ? "This AccessError usually means missing write ACL on res.partner [1]."
            : "Selection fields constrain workflow states on custom models [1].",
          citations: [
            {
              source: "project",
              version: "all",
              breadcrumb: "Security model",
              chunk_id: "expert-e2e-1",
              source_index: 1,
            },
          ],
          grounded: true,
          declined: false,
          suggested_tools: [],
          caution_flags: isError ? ["access"] : [],
        }),
      });
    });
  });

  test("explain-this opens expert with prefilled question", async ({ page }) => {
    await page.goto("/e2e/expert");
    await expect(page.getByTestId("expert-harness")).toBeVisible();
    await page.getByTestId("explain-this").click();
    await expect(page.getByTestId("expert-panel")).toBeVisible();
    await expect(page.getByTestId("expert-input")).toHaveValue(/x_status/);
    await page.getByRole("button", { name: "Ask Expert" }).click();
    await expect(page.getByText("Grounded")).toBeVisible();
    await expect(page.getByText(/Selection fields constrain/)).toBeVisible();
    await page.screenshot({
      path: path.join(OUT_DIR, "expert-explain-this.png"),
      fullPage: true,
    });
  });

  test("error notice diagnose auto-submits with error in main input", async ({ page }) => {
    await page.goto("/e2e/expert");
    await page.getByRole("button", { name: /Diagnose with Expert/i }).click();
    await expect(page.getByTestId("expert-panel")).toBeVisible();
    await expect(page.getByTestId("expert-input")).toHaveValue(/Error log:/);
    await expect(page.getByTestId("expert-input")).toHaveValue(/AccessError/);
    await expect(page.getByText(/AccessError usually means/)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("expert-copy-answer")).toBeVisible();
    await page.screenshot({
      path: path.join(OUT_DIR, "expert-error-diagnose.png"),
      fullPage: true,
    });
  });
});
