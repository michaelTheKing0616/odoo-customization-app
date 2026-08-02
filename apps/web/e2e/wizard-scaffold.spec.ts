import { expect, test } from "@playwright/test";

const PHRASE = "I understand the risks";
const CONN = "test-conn";

test.describe("Wizard scaffold", () => {
  test.beforeEach(async ({ page }) => {
    // Catch API whether absolute or relative
    await page.route("**/api/connections/**", async (route) => {
      const url = route.request().url();
      if (url.includes("/apps/scaffold") && route.request().method() === "POST") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            ok: true,
            template_id: "library",
            models: ["x_lib_category", "x_lib_author", "x_lib_book", "x_lib_loan"],
            models_created: ["x_lib_category", "x_lib_author", "x_lib_book", "x_lib_loan"],
            models_skipped: [],
            fields_created: 12,
            menus_created: 4,
            view_injects: 3,
            message: "Library scaffolded",
            warnings: [],
          }),
        });
        return;
      }
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
      await route.continue();
    });

    await page.route("**/api/apps/templates", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "library",
            name: "Library",
            description: "Books, categories, and loans with member tracking.",
          },
          {
            id: "crm_lite",
            name: "CRM Lite",
            description: "Lightweight leads with partner and stage.",
          },
        ]),
      });
    });

    await page.route("**/api/ai/status", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ai_assist: "off",
          enabled: false,
          ollama_base_url: "http://127.0.0.1:11434",
          ollama_model: "llama3.2",
          ollama_reachable: false,
          ollama_detail: "disabled",
        }),
      });
    });
  });

  test("Library card scaffolds and shows checklist", async ({ page }) => {
    await page.goto(`/connections/${CONN}/wizard`);

    await expect(page.getByRole("heading", { name: "App wizard" })).toBeVisible();
    const libraryCard = page.getByTestId("template-card-library");
    await expect(libraryCard).toBeVisible();
    await libraryCard.click();
    await expect(page.getByTestId("confirm-dialog")).toBeVisible();

    await page.getByTestId("confirm-dialog-input").fill(PHRASE);
    await page.getByTestId("confirm-dialog-confirm").click();

    await expect(page.getByTestId("scaffold-result")).toBeVisible();
    await expect(page.getByTestId("scaffold-checklist")).toBeVisible();
    await expect(page.getByTestId("scaffold-models")).toContainText("x_lib_book");
    await expect(page.getByTestId("scaffold-checklist")).toContainText(
      "Models created",
    );
    await expect(page.getByTestId("scaffold-checklist")).toContainText(
      "Menus created",
    );
    await expect(page.getByTestId("scaffold-checklist")).toContainText(
      "Open designer",
    );
    await expect(page.getByTestId("scaffold-checklist")).toContainText(
      "Run sandbox",
    );
  });
});
