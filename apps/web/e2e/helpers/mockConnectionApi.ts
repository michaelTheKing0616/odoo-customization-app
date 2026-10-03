import type { Page } from "@playwright/test";

export const DEMO_CONN = {
  id: "demo-conn",
  name: "Demo",
  url: "http://127.0.0.1:8069",
  db_name: "odoo",
  username: "admin",
  server_version: "19.0",
  write_mode: "standard",
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

const PRODUCTION_READINESS = {
  passed: false,
  items: [
    {
      key: "snapshot_drill",
      label: "Snapshot drill",
      detail: "Mock checklist for vision-verify.",
      status: "warn" as const,
    },
  ],
};

/** Intercept FastAPI calls for shell + primary pages (any NEXT_PUBLIC_API_URL host). */
export async function mockConnectionApi(page: Page) {
  await page.route("**/api/admin/**", async (route) => {
    const url = route.request().url();
    if (url.includes("/trust-telemetry")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ workspaces: [] }),
      });
      return;
    }
    if (url.includes("/ga-criteria")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          min_beta_partner_workspaces: 0,
          min_weeks_per_workspace: 0,
          production_write_mode_ga_unlocked: false,
          exit_criteria: ["Mock GA criteria for e2e."],
        }),
      });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });

  await page.route("**/api/pipelines**", async (route) => {
    const url = route.request().url();
    if (url.match(/\/hops(\?|$)/)) {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });

  await page.route("**/api/trust/safety**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        markdown: "## Safety contract\n\nMock trust copy for e2e.",
        source: "mock",
      }),
    });
  });

  await page.route("**/api/live-demo-copilot/**", async (route) => {
    const url = route.request().url();
    if (url.includes("/disclosure")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          version: "mock-1",
          title: "Meeting assist disclosure",
          summary: "Mock disclosure for e2e.",
          bullets: ["Attendee bot is visible to participants.", "Answers stay private to you."],
          opt_out: "You can decline and end the session at any time.",
          retention_default: "do_not_retain",
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: "mock-session", status: "draft", mock_mode: true }),
    });
  });

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
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ recipes: [] }),
      });
      return;
    }
    if (url.match(/\/power-ops\/capabilities(\?|$)/)) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ power_ops_recipes: [] }),
      });
      return;
    }

    if (url.match(/\/models(\?|$)/)) {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
      return;
    }

    if (url.match(/\/modules\/promoted(\?|$)/)) {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
      return;
    }

    if (url.match(/\/modules(\?|$)/)) {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
      return;
    }

    if (url.match(/\/production-readiness(\?|$)/)) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(PRODUCTION_READINESS),
      });
      return;
    }

    if (url.match(/\/ee-playbooks(\?|$)/)) {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
      return;
    }

    if (url.match(/\/domain-playbooks(\?|$)/)) {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
      return;
    }

    if (url.match(/\/health-check\/latest(\?|$)/)) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(null),
      });
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

    if (url.match(/\/config\/website\/pages(\?|$)/)) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          available: true,
          reason: null,
          pages: [],
          menus: null,
        }),
      });
      return;
    }

    const fallback = connectionApiFallback(url);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(fallback),
    });
  });

  await page.route("**/api/auth/**", async (route) => {
    const url = route.request().url();
    if (url.includes("/status")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          auth_mode: "off",
          auth_enabled: false,
          active_keys: 0,
          env_key_configured: false,
          bootstrap_available: false,
        }),
      });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
}

const EMPTY_GATING = {
  available: true,
  title: "",
  why: "",
  options: [],
  gating_choices: [],
};

function connectionApiFallback(url: string): unknown {
  if (url.match(/\/power-ops\/recipes(\?|$)/)) {
    return { recipes: [] };
  }
  if (url.match(/\/power-ops\/capabilities(\?|$)/)) {
    return { power_ops_recipes: [] };
  }
  if (url.match(/\/code-studio\/gate(\?|$)/)) {
    return {
      probe: { supported: true },
      gating: EMPTY_GATING,
      developer_role_required: false,
      entitlement_key: "code_studio",
    };
  }
  if (url.match(/\/code-studio\/context(\?|$)/)) {
    return { symbols: [], models: [] };
  }
  if (url.match(/\/code-studio\/snippets(\?|$)/)) {
    return { snippets: [] };
  }
  if (url.match(/\/bulk\/crons(\?|$)/)) {
    return { crons: [], probe: { supported: true } };
  }
  if (url.match(/\/script-runner\/templates(\?|$)/)) {
    return { templates: [] };
  }
  if (url.match(/\/script-runner\/(library|runs)(\?|$)/)) {
    return [];
  }
  if (url.match(/\/batch-os\/atlas\/search(\?|$)/)) {
    return { hits: [] };
  }
  if (url.match(/\/batch-os\/atlas(\?|$)/)) {
    return { classes: [], honesty: "mock atlas for e2e" };
  }
  if (url.match(/\/batch-os\/recipes(\?|$)/)) {
    return [];
  }
  if (url.match(/\/config\/recipes(\?|$)/)) {
    return [];
  }
  if (url.match(/\/config\//)) {
    if (url.includes("/languages")) {
      return [{ id: 1, code: "en_US", name: "English (US)", active: true }];
    }
    if (url.includes("/i18n")) return { ok: true, method: "mock", message: "ok", major: 19 };
    return [];
  }
  return [];
}
