import { expect, test } from "@playwright/test";

const CONN = "test-conn";

const MOCK_CAPS = {
  major: 19,
  edition: "community",
  server_version: "19.0",
  supported: [
    "object_create_crud_model",
    "object_write_update_path",
    "related_write_dotted_path",
    "view_inject_inherit",
    "view_inject_mutate",
    "base_automation_safe_triggers",
  ],
  unsupported: [],
  ga: true,
  message: "ok",
};

test.describe("Wizard component flow", () => {
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
            capabilities: MOCK_CAPS,
          }),
        });
        return;
      }
      if (url.includes("/models") && route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([{ model: "project.task", name: "Task" }]),
        });
        return;
      }
      await route.continue();
    });

    await page.route("**/api/apps/templates", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    await page.route("**/api/ai/status", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ enabled: true, ollama_reachable: true }),
      });
    });

    await page.route("**/api/ai/component-gallery", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "inspection_checklist",
            name: "Inspection checklist",
            description: "Checklist on project tasks",
            host_slot: "project.task",
          },
        ]),
      });
    });

    await page.route("**/api/ai/propose-connect-points", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: true,
          grain: "feature_slice",
          grain_label: "Component for Task",
          requires_review: true,
          connect_points: {
            host_model: "project.task",
            form_xpath: "//sheet",
            host_module: "project",
          },
          host_candidates: [{ model: "project.task", label: "Task", score: 1 }],
          gallery_id: "inspection_checklist",
        }),
      });
    });

    await page.route("**/api/ai/draft-module", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: true,
          grain: "feature_slice",
          grain_label: "Component for Task",
          draft: {
            grain: "feature_slice",
            _component: true,
            technical_name: "ext_project_task",
            models: [{ model: "project.task", mode: "inherit", fields: [] }],
            connect_points: { host_model: "project.task" },
          },
          warnings: [],
          refusals: [],
        }),
      });
    });
  });

  test("connect-points review gates draft then shows component actions", async ({ page }) => {
    await page.goto(`/connections/${CONN}/wizard`);
    await expect(page.getByTestId("draft-studio")).toBeVisible();

    await page.getByPlaceholder(/Car rental fleet/i).fill(
      "add inspection checklist to project tasks",
    );

    await page.getByLabel("Grain override").selectOption("feature_slice");
    await page.getByTestId("review-connect-points").click();
    await expect(page.getByTestId("connect-points-review")).toBeVisible();

    const draftBtn = page.getByTestId("create-draft");
    await expect(draftBtn).toBeDisabled();

    await page.getByRole("button", { name: "Approve connect points" }).click();
    await expect(draftBtn).toBeEnabled();
    await draftBtn.click();

    await expect(page.getByTestId("draft-model-review")).toBeVisible();
    await expect(page.getByRole("button", { name: "Suggest as template" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Save as component" })).toBeVisible();
  });
});
