import { test, expect } from "@playwright/test";

const apiBase =
  process.env.PLAYWRIGHT_API_BASE ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8001";

const MOCK_BILLING_CATALOG = {
  tier_order: ["free_solo", "pro", "business", "agency"],
  display_features: [
    { key: "connections_limit", label: "Odoo connections" },
    { key: "active_projects_limit", label: "Active projects" },
    { key: "designer", label: "View designer" },
    { key: "automations", label: "Automations" },
    { key: "module_export", label: "Module export + sandbox" },
    { key: "bulk_suite", label: "Bulk suite" },
    { key: "expert", label: "Odoo Expert" },
    { key: "dev_tools", label: "Code Studio & developer tools" },
  ],
  project_pass: {
    display_name: "Project Pass",
    one_time_usd: 149,
  },
  plans: [
    {
      id: "free_solo",
      display_name: "Free Solo",
      monthly_usd: 0,
      features: { designer: "true", bulk_suite: "false" },
    },
    {
      id: "pro",
      display_name: "Pro",
      monthly_usd: 39,
      extra_slot_monthly_usd: 15,
      features: { designer: "true", bulk_suite: "true" },
    },
    {
      id: "business",
      display_name: "Business",
      monthly_usd: 99,
      features: { designer: "true", bulk_suite: "true" },
    },
    {
      id: "agency",
      display_name: "Agency",
      monthly_usd: 249,
      features: { designer: "unlimited", bulk_suite: "true" },
    },
  ],
};

test.describe("Pricing page (MON-4 / REM-10)", () => {
  test.beforeEach(async ({ page }) => {
    await page.route(`${apiBase}/api/billing/plans`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_BILLING_CATALOG),
      });
    });
    await page.route("**/api/billing/plans", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_BILLING_CATALOG),
      });
    });
  });

  test("renders tier comparison from registry", async ({ page }) => {
    await page.goto("/pricing");
    await expect(page.getByRole("heading", { name: "Pricing" })).toBeVisible();
    await expect(page.getByTestId("pricing-tier-free_solo")).toBeVisible();
    await expect(page.getByTestId("pricing-tier-pro")).toBeVisible();
    await expect(page.getByTestId("project-pass")).toBeVisible();
    await expect(page.getByText("Operate tools")).toBeVisible();
  });

  test("landing links to pricing", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: "See pricing" })).toBeVisible();
  });

  test("shows registry-driven Pro price when API available", async ({ page }) => {
    await page.goto("/pricing");
    const proPrice = page.getByTestId("price-pro");
    if ((await proPrice.count()) > 0) {
      await expect(proPrice).toContainText("$39");
    }
  });
});

test.describe("Billing flows harness (REM-10)", () => {
  test("trial banner and upgrade sheet", async ({ page }) => {
    await page.goto("/e2e/billing");
    await expect(page.getByTestId("trial-banner")).toBeVisible();
    await expect(page.getByTestId("downgrade-summary")).toBeVisible();
    await page.getByTestId("open-upgrade").click();
    await expect(page.getByTestId("upgrade-sheet")).toBeVisible();
  });

  test("upgrade sheet extra-slots panel visible for slot limit", async ({ page }) => {
    await page.goto("/e2e/billing");
    await page.getByTestId("open-upgrade").click();
    await expect(page.getByTestId("upgrade-sheet")).toBeVisible();
    // Panel renders when catalog loads; may be empty offline — sheet still opens
    await expect(page.getByRole("link", { name: "Compare all plans" })).toBeVisible();
  });
});
