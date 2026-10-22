import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";
import path from "node:path";
import { mockConnectionApi } from "./helpers/mockConnectionApi";

/** UI-F03 evidence: axe + desktop/390 screenshots for the pages whose loading and empty states moved to the kit. */
const OUT_DIR = path.resolve(__dirname, "../../../docs/vision-verify/UI-F03");
const VIEWPORTS = [
  { suffix: "desktop", width: 1440, height: 900 },
  { suffix: "390", width: 390, height: 844 },
] as const;

type Target = {
  slug: string;
  path: string;
  state?: "loading" | "empty";
  /** Extra page.route overrides, registered after the shared mock so they win. */
  setup?: (page: Page) => Promise<void>;
  ready: (page: Page) => Promise<void>;
};

const hang = async (page: Page, pattern: string) => {
  await page.route(pattern, () => undefined);
};

const json = (body: unknown) => ({ status: 200, contentType: "application/json", body: JSON.stringify(body) });

/** Endpoints these pages call that the shared mock does not shape (audit log, plan diff). */
async function mockUiF03Endpoints(page: Page) {
  await page.route("**/api/audit/logs**", (route) =>
    route.fulfill(
      json([
        {
          id: "audit-1",
          method: "POST",
          path: "/api/connections/demo-conn/fields",
          status_code: 200,
          duration_ms: 142,
          created_at: "2026-10-05T12:00:00Z",
        },
      ]),
    ),
  );
  await page.route("**/api/billing/plan-diff**", (route) =>
    route.fulfill(json({ from_plan: "internal", to_plan: "free_solo", lost_features: [] })),
  );
}

const TARGETS: Target[] = [
  {
    slug: "settings",
    path: "/settings",
    ready: async (page) => {
      await expect(page.getByTestId("settings-page")).toBeVisible();
      await expect(page.getByText("/api/connections/demo-conn/fields")).toBeVisible();
    },
  },
  {
    slug: "settings",
    path: "/settings",
    state: "loading",
    setup: (page) => hang(page, "**/api/auth/status"),
    ready: async (page) => {
      await expect(page.getByTestId("settings-status-loading")).toBeVisible();
      await expect(page.getByTestId("settings-audit-loading")).toBeVisible();
    },
  },
  {
    slug: "settings",
    path: "/settings",
    state: "empty",
    setup: async (page) => {
      await page.addInitScript(() => window.localStorage.setItem("odoo_custom_api_key", "oc_e2e_key"));
      await page.route("**/api/audit/logs**", (route) => route.fulfill(json([])));
      await page.route("**/api/auth/status", (route) =>
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            auth_mode: "api_key",
            auth_enabled: true,
            active_keys: 0,
            env_key_configured: false,
            bootstrap_available: false,
          }),
        }),
      );
    },
    ready: async (page) => {
      await expect(page.getByRole("heading", { name: "No API keys yet" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "No audit entries yet" })).toBeVisible();
    },
  },
  {
    slug: "settings-billing",
    path: "/settings/billing",
    ready: async (page) => {
      await expect(page.getByRole("button", { name: "Manage billing" })).toBeVisible();
    },
  },
  {
    slug: "settings-billing",
    path: "/settings/billing",
    state: "loading",
    setup: (page) => hang(page, "**/api/billing/entitlements"),
    ready: async (page) => {
      await expect(page.getByTestId("billing-plan-loading")).toBeVisible();
    },
  },
  {
    slug: "settings-billing",
    path: "/settings/billing",
    state: "empty",
    setup: async (page) => {
      await page.route("**/api/billing/entitlements", (route) =>
        route.fulfill({ status: 401, contentType: "application/json", body: '{"detail":"Sign in"}' }),
      );
    },
    ready: async (page) => {
      await expect(page.getByRole("heading", { name: "No plan to show" })).toBeVisible();
    },
  },
  {
    slug: "settings-trust-safety",
    path: "/settings/trust-safety",
    ready: async (page) => {
      await expect(page.getByRole("heading", { name: "Safety contract" })).toBeVisible();
    },
  },
  {
    slug: "settings-trust-safety",
    path: "/settings/trust-safety",
    state: "loading",
    setup: (page) => hang(page, "**/api/trust/safety**"),
    ready: async (page) => {
      await expect(page.getByTestId("trust-safety-loading")).toBeVisible();
    },
  },
  {
    slug: "admin",
    path: "/admin",
    ready: async (page) => {
      await expect(page.getByTestId("admin-console")).toBeVisible();
      await expect(page.getByRole("heading", { name: "No workspaces to report on" })).toBeVisible();
    },
  },
  {
    slug: "admin",
    path: "/admin",
    state: "loading",
    setup: (page) => hang(page, "**/api/admin/**"),
    ready: async (page) => {
      await expect(page.getByTestId("admin-users-loading")).toBeVisible();
    },
  },
  {
    slug: "pipelines",
    path: "/pipelines",
    ready: async (page) => {
      await expect(page.getByRole("heading", { name: "No pipelines yet" })).toBeVisible();
    },
  },
  {
    slug: "pipelines",
    path: "/pipelines",
    state: "loading",
    setup: (page) => hang(page, "**/api/pipelines"),
    ready: async (page) => {
      await expect(page.getByTestId("pipelines-list-loading")).toBeVisible();
    },
  },
];

async function seriousAxeViolations(page: Page, label: string) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .exclude('[data-testid="app-topbar"]')
    .disableRules(["document-title", "html-has-lang", "label"])
    .analyze();
  fs.appendFileSync(
    path.join(OUT_DIR, "axe-results.jsonl"),
    `${JSON.stringify({ label, violations: results.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length })) })}\n`,
  );
  return results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
}

function fileName(target: Target, suffix: string) {
  return `${target.slug}${target.state ? `-${target.state}` : ""}-${suffix}.png`;
}

test.describe("UI-F03 kit states — axe and vision evidence (mocked API)", () => {
  test.describe.configure({ timeout: 90_000 });

  test.beforeAll(() => {
    fs.mkdirSync(OUT_DIR, { recursive: true });
  });

  for (const target of TARGETS) {
    for (const vp of VIEWPORTS) {
      const label = `${target.path}${target.state ? ` (${target.state})` : ""} @${vp.suffix}`;
      test(`${label} passes axe and is captured`, async ({ page }) => {
        await page.setViewportSize({ width: vp.width, height: vp.height });
        await page.emulateMedia({ reducedMotion: "reduce" });
        await mockConnectionApi(page);
        await mockUiF03Endpoints(page);
        if (target.setup) await target.setup(page);
        await page.goto(target.path);
        await target.ready(page);
        await page.screenshot({ path: path.join(OUT_DIR, fileName(target, vp.suffix)), fullPage: true });
        const serious = await seriousAxeViolations(page, label);
        expect(serious, `${label} axe violations: ${JSON.stringify(serious, null, 2)}`).toEqual([]);
      });
    }
  }

  for (const vp of VIEWPORTS) {
    test(`connection shell loading skeleton @${vp.suffix} passes axe and is captured`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.emulateMedia({ reducedMotion: "reduce" });
      await mockConnectionApi(page);
      await page.route(/\/api\/connections\/demo-conn(\?.*)?$/, () => undefined);
      await page.goto("/connections/demo-conn");
      await expect(page.getByTestId("app-shell-loading")).toBeVisible({ timeout: 45_000 });
      await page.screenshot({ path: path.join(OUT_DIR, `connection-shell-loading-${vp.suffix}.png`), fullPage: true });
      const serious = await seriousAxeViolations(page, `/connections/demo-conn (shell loading) @${vp.suffix}`);
      expect(serious, `shell loading axe violations: ${JSON.stringify(serious, null, 2)}`).toEqual([]);
    });
  }
});
