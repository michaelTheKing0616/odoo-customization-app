import type { Page } from "@playwright/test";

export const DEMO_CONN = {
  id: "demo-conn",
  name: "Demo",
  url: "http://127.0.0.1:8069",
  db_name: "odoo",
  username: "admin",
  server_version: "19.0",
  created_at: null,
  updated_at: null,
  capabilities: {
    major: 19,
    edition: "community",
    server_version: "19.0",
    supported: [
      "view_inject_inherit",
      "base_automation_safe_triggers",
      "bulk_transition",
      "power_ops",
    ],
    unsupported: [],
    ga: true,
    message: "ok",
    hosting_hint: "self_hosted",
    installed_modules_sample: ["base", "web", "mail"],
  },
};

/** Intercept FastAPI calls (NEXT_PUBLIC_API_URL defaults to :8000) for shell + primary pages. */
export async function mockConnectionApi(page: Page) {
  await page.route("**/api/billing/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        workspace_id: "demo-ws",
        plan_id: "internal",
        subscription_status: "active",
        features: {},
        extra_project_slots: 0,
        active_projects: 0,
        active_project_limit: null,
        trial_ends_at: null,
        current_period_end: null,
      }),
    });
  });

  await page.route("**/api/connections/**", async (route) => {
    const url = route.request().url();

    if (url.endsWith("/connections") || url.match(/\/api\/connections$/)) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([DEMO_CONN]),
      });
      return;
    }

    if (url.match(/\/demo-conn(\?|$)/)) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(DEMO_CONN),
      });
      return;
    }

    if (url.match(/\/automations\/gate(\?|$)/)) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          automations: {
            available: true,
            title: "",
            why: "",
            options: [],
            gating_choices: [],
          },
          approvals: {
            available: true,
            title: "",
            why: "",
            options: [],
            gating_choices: [],
          },
        }),
      });
      return;
    }

    if (url.match(/\/power-ops\/recipes(\?|$)/)) {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
      return;
    }

    if (url.match(/\/models(\?|$)/)) {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
      return;
    }

    if (url.match(/\/modules(\?|$)/)) {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
      return;
    }

    if (url.match(/\/snapshots(\?|$)/)) {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
      return;
    }

    if (url.match(/\/audit/)) {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
      return;
    }

    if (url.match(/\/health-check/)) {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
      return;
    }

    if (url.match(/\/migration-assist(\?|$)/)) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(null),
      });
      return;
    }

    if (url.match(/\/deployment-panel(\?|$)/)) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(null),
      });
      return;
    }

    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
}
