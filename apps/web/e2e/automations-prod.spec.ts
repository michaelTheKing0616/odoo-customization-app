import { expect, test, type Page } from "@playwright/test";

const CONN = "e2e-automations-prod";

function caps16() {
  return {
    major: 16,
    edition: "community",
    server_version: "16.0",
    supported: [
      "base_automation_safe_triggers",
      "view_inject_inherit",
      "object_create_crud_model",
      "list_tree_fallback",
    ],
    unsupported: [
      {
        id: "related_write_dotted_path",
        label: "Related write",
        reason: "Not on 16",
      },
      {
        id: "object_write_update_path",
        label: "Update field",
        reason: "Not on 16",
      },
    ],
    ga: false,
    message: "Odoo 16 experimental",
    hosting_hint: "self_hosted",
    python_module_install: true,
    installed_modules_sample: ["base", "web"],
    warnings: [],
  };
}

function caps19() {
  return {
    major: 19,
    edition: "community",
    server_version: "19.0",
    supported: [
      "related_write_dotted_path",
      "object_write_update_path",
      "object_create_crud_model",
      "base_automation_safe_triggers",
      "view_inject_inherit",
      "view_inject_mutate",
      "smart_button_inherit_box",
      "list_as_list_type",
      "list_tree_fallback",
    ],
    unsupported: [],
    ga: true,
    message: "Odoo 19 GA",
    hosting_hint: "self_hosted",
    python_module_install: true,
    installed_modules_sample: ["base", "web"],
    warnings: [],
  };
}

async function mockAutomationsApi(page: Page, caps: ReturnType<typeof caps16>) {
  await page.route("**/api/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    if (method === "GET" && url.includes("/api/connections") && !url.includes(CONN)) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: CONN,
            name: "E2E Automations",
            url: "http://127.0.0.1:8069",
            db_name: "odoo_dev",
            username: "admin",
            server_version: caps.server_version,
            created_at: null,
            updated_at: null,
            capabilities: caps,
          },
        ]),
      });
      return;
    }
    if (url.includes(`/api/connections/${CONN}/automations`) && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: "[]",
      });
      return;
    }
    if (url.includes("activity-types") || url.includes("snapshots")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: "[]",
      });
      return;
    }
    if (url.includes(`/api/connections/${CONN}`) && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: CONN,
          name: "E2E Automations",
          url: "http://127.0.0.1:8069",
          db_name: "odoo_dev",
          username: "admin",
          server_version: caps.server_version,
          created_at: null,
          updated_at: null,
          capabilities: caps,
        }),
      });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
}

test.describe("Production Automations page (mocked API)", () => {
  test("Odoo 16 greys out update_field and related_write on real route", async ({
    page,
  }) => {
    await mockAutomationsApi(page, caps16());
    await page.goto(`/connections/${CONN}/automations`);
    await expect(page.getByTestId("automations-form")).toBeVisible();
    const select = page.getByTestId("automation-action-kind");
    await expect(select.locator('option[value="update_field"]')).toHaveAttribute(
      "disabled",
      "",
    );
    await expect(select.locator('option[value="related_write"]')).toHaveAttribute(
      "disabled",
      "",
    );
    await expect(
      select.locator('option[value="create_activity"]'),
    ).not.toHaveAttribute("disabled", "");
  });

  test("Odoo 19 enables update_path actions on real route", async ({ page }) => {
    await mockAutomationsApi(page, caps19());
    await page.goto(`/connections/${CONN}/automations`);
    await expect(page.getByTestId("automations-form")).toBeVisible();
    const select = page.getByTestId("automation-action-kind");
    await expect(select.locator('option[value="update_field"]')).not.toHaveAttribute(
      "disabled",
      "",
    );
    await expect(select.locator('option[value="related_write"]')).not.toHaveAttribute(
      "disabled",
      "",
    );
  });
});
