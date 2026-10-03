import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mockConnectionApi } from "./helpers/mockConnectionApi";

async function expectNoSeriousAxeViolations(page: Page, label: string) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .exclude('[data-testid="app-topbar"]')
    .disableRules(["document-title", "html-has-lang", "label"])
    .analyze();
  const serious = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical",
  );
  expect(serious, `${label} axe violations: ${JSON.stringify(serious, null, 2)}`).toEqual([]);
}

type PrimaryPage = {
  path: string;
  label: string;
  testId?: string;
  heading?: string;
  /** Connection shell routes render AppShell; harness and govern pages do not. */
  appShell?: boolean;
};

/** Operate + govern routes from spec 13 with a real page or /e2e harness twin (UI-F12). */
const PRIMARY_PAGES: PrimaryPage[] = [
  // Connection operate (mocked API)
  { path: "/connections/demo-conn", testId: "connection-overview", label: "Overview" },
  { path: "/connections/demo-conn/builder", testId: "builder-page", label: "Builder" },
  { path: "/e2e/designer", testId: "designer-harness", label: "Designer", appShell: false },
  { path: "/connections/demo-conn/menus", testId: "menus-page", label: "Menus" },
  { path: "/connections/demo-conn/website", testId: "website-editor-page", label: "Website" },
  { path: "/connections/demo-conn/automations", testId: "automations-page", label: "Automations" },
  { path: "/connections/demo-conn/approvals", testId: "approvals-page", label: "Odoo approval rules" },
  { path: "/connections/demo-conn/reports", testId: "reports-page", label: "Reports" },
  { path: "/connections/demo-conn/code-studio", testId: "code-studio-page", label: "Code Studio" },
  { path: "/connections/demo-conn/access", testId: "access-page", label: "Access" },
  { path: "/connections/demo-conn/studio", testId: "studio-page", label: "App Studio" },
  { path: "/connections/demo-conn/wizard", testId: "draft-studio", label: "Wizard" },
  { path: "/connections/demo-conn/job", testId: "job-autopilot", label: "Job Autopilot" },
  { path: "/e2e/modulespec", testId: "modulespec-page", label: "ModuleSpec", appShell: false },
  { path: "/e2e/projects", testId: "projects-page", label: "Projects", appShell: false },
  { path: "/connections/demo-conn/expert", testId: "expert-destination", label: "Expert" },
  { path: "/connections/demo-conn/import", testId: "import-page", label: "Import" },
  { path: "/connections/demo-conn/id-generator", testId: "id-generator-page", label: "ID Generator" },
  { path: "/connections/demo-conn/ingest", testId: "ingest-page", label: "Ingest" },
  { path: "/connections/demo-conn/operations", testId: "operations-hub", label: "Operations hub" },
  { path: "/connections/demo-conn/bulk-suite", testId: "bulk-suite-page", label: "Bulk Suite" },
  { path: "/connections/demo-conn/power-ops", testId: "power-ops-page", label: "Power Ops" },
  { path: "/connections/demo-conn/cron-manager", testId: "cron-manager-page", label: "Cron Manager" },
  { path: "/connections/demo-conn/housekeeping", testId: "housekeeping-page", label: "Housekeeping" },
  { path: "/connections/demo-conn/reminders", testId: "reminders-page", label: "Reminders" },
  { path: "/connections/demo-conn/script-runner", testId: "script-runner-page", label: "Script Runner" },
  { path: "/connections/demo-conn/config", testId: "config-page", label: "Config" },
  {
    path: "/connections/demo-conn/live-demo-copilot",
    testId: "live-demo-copilot-page",
    label: "Live Demo Co-Pilot",
  },
  { path: "/connections/demo-conn/journal", testId: "journal-page", label: "Journal" },
  { path: "/e2e/overlay", testId: "overlay-harness", label: "Presenter overlay", appShell: false },
  // Settings, admin, pipelines, connect, seeded govern
  { path: "/connect", testId: "connect-secret", label: "Connect", appShell: false },
  { path: "/settings", testId: "settings-page", label: "Settings", appShell: false },
  { path: "/e2e/billing", testId: "downgrade-summary", label: "Billing", appShell: false },
  { path: "/settings/trust-safety", testId: "trust-safety-page", label: "Trust & safety", appShell: false },
  { path: "/admin", testId: "admin-console", label: "Admin", appShell: false },
  { path: "/pipelines", testId: "pipelines-page", label: "Pipelines", appShell: false },
  { path: "/approvals", testId: "approvals-inbox-page", label: "Approval inbox", appShell: false },
  { path: "/command", heading: "Command center", label: "Command center", appShell: false },
  {
    path: "/bridge/contracts/new",
    heading: "Contract Studio",
    label: "Bridge contract",
    appShell: false,
  },
];

function usesAppShell(target: PrimaryPage): boolean {
  if (target.appShell !== undefined) return target.appShell;
  return target.path.startsWith("/connections/demo-conn");
}

async function expectPageReady(page: Page, target: PrimaryPage) {
  if (usesAppShell(target)) {
    await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 45_000 });
  }
  if (target.testId) {
    await expect(page.getByTestId(target.testId)).toBeVisible({ timeout: 30_000 });
  } else if (target.heading) {
    await expect(page.getByRole("heading", { name: target.heading })).toBeVisible({
      timeout: 30_000,
    });
  } else {
    throw new Error(`Primary page ${target.label} needs testId or heading`);
  }
}

test.describe("UIX-5 a11y — primary pages (mocked API)", () => {
  test.describe.configure({ timeout: 90_000 });

  test.beforeEach(async ({ page }) => {
    await mockConnectionApi(page);
  });

  for (const target of PRIMARY_PAGES) {
    test(`${target.label} renders and passes axe`, async ({ page }) => {
      await page.goto(target.path);
      await expectPageReady(page, target);
      await expectNoSeriousAxeViolations(page, target.label);
    });
  }
});
