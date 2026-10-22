import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/** UI-S-42 Billing desk via the /e2e/billing?state=... harness (real registry prices). */

const open = async (page: import("@playwright/test").Page, state: string) => {
  await page.goto(`/e2e/billing?state=${state}`);
  await expect(page.getByTestId("billing-page")).toBeVisible({ timeout: 120_000 });
};

test.describe("Billing desk (UI-S-42)", () => {
  test("paid plan: one teal Manage plan, real price, receipt estimate", async ({ page }) => {
    await open(page, "active");
    const desk = page.getByTestId("billing-page");
    await expect(desk.locator("button.bg-accent")).toHaveCount(1);
    await expect(page.getByTestId("billing-manage-plan")).toHaveText(/Manage plan/);
    await expect(page.getByTestId("billing-plan-price")).toContainText("$39");
    await expect(page.getByTestId("billing-charge")).toContainText("$69.00");
    await expect(page.getByTestId("billing-charge")).toContainText("Stripe invoice is final");
    await expect(page.getByTestId("trial-banner")).toHaveCount(0);
    await expect(page.getByRole("meter", { name: "Active project slots used" })).toBeVisible();
  });

  test("free plan: Manage plan unfolds the chooser with real tier prices", async ({ page }) => {
    await open(page, "free");
    const primary = page.getByTestId("billing-manage-plan");
    await expect(primary).toHaveAttribute("aria-expanded", "false");
    await primary.click();
    await expect(primary).toHaveAttribute("aria-expanded", "true");
    const chooser = page.getByTestId("billing-plan-chooser");
    await expect(chooser).toContainText("$39");
    await expect(chooser).toContainText("$149");
    await expect(chooser).toContainText("$399");
    await expect(chooser.getByRole("button", { name: "Continue with Pro" })).toBeFocused();
  });

  test("past due: danger notice and payment action", async ({ page }) => {
    await open(page, "past-due");
    await expect(page.getByTestId("billing-risk-payment")).toContainText("Last payment failed");
    await expect(page.getByTestId("billing-charge")).toContainText("Unpaid invoice");
    await expect(page.getByRole("button", { name: "Update payment method" })).toBeVisible();
  });

  test("internal: Manage plan disabled with a reason", async ({ page }) => {
    await open(page, "internal");
    await expect(page.getByTestId("billing-manage-plan")).toBeDisabled();
    await expect(page.getByTestId("billing-charge")).toContainText("Not billed");
  });

  test("portal error sits next to Manage billing and offers the chooser", async ({ page }) => {
    await open(page, "portal-error");
    const err = page.getByTestId("billing-payment").getByTestId("billing-action-error");
    await expect(err).toContainText("No Stripe customer on file yet");
    await err.getByRole("button", { name: "Choose a plan" }).click();
    await expect(page.getByTestId("billing-plan-chooser")).toBeVisible();
  });

  test("load error and signed-out empty keep their recovery actions", async ({ page }) => {
    await open(page, "error");
    await expect(page.getByTestId("billing-plan-error")).toContainText("We couldn't load your plan.");
    await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
    await open(page, "empty");
    await expect(page.getByRole("heading", { name: "No plan to show" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
  });

  test("390px reflow without horizontal scroll and no em dashes", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    for (const state of ["trial", "choose", "past-due"]) {
      await open(page, state);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow, state).toBeLessThanOrEqual(0);
      const text = await page.getByTestId("billing-page").innerText();
      expect(text, state).not.toMatch(/[\u2014\u2013]/);
    }
  });

  test("axe: no serious or critical issues on trial and choose", async ({ page }) => {
    for (const state of ["trial", "choose", "portal-error"]) {
      await open(page, state);
      const results = await new AxeBuilder({ page }).include('[data-testid="billing-page"]').analyze();
      const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
      expect(bad.map((v) => `${state}: ${v.id}`)).toEqual([]);
    }
  });

  test("real route /settings/billing: plan desk from mocked entitlements and catalog", async ({ page }) => {
    const json = (body: unknown) => ({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    await page.route("**/api/billing/**", (route) => {
      const url = route.request().url();
      if (url.includes("/api/billing/plans")) {
        return route.fulfill(
          json({
            tier_order: ["free_solo", "pro", "business", "agency"],
            display_features: [{ key: "bulk_suite", label: "Bulk suite" }],
            project_pass: { display_name: "Project Pass", one_time_usd: 299 },
            plans: [
              { id: "free_solo", display_name: "Free Solo", monthly_usd: 0, extra_slot_monthly_usd: null, features: { bulk_suite: "false" } },
              { id: "pro", display_name: "Pro", monthly_usd: 39, extra_slot_monthly_usd: 15, features: { bulk_suite: "false" } },
              { id: "business", display_name: "Business", monthly_usd: 149, extra_slot_monthly_usd: 10, features: { bulk_suite: "true" } },
              { id: "agency", display_name: "Agency", monthly_usd: 399, extra_slot_monthly_usd: null, features: { bulk_suite: "true" } },
            ],
          }),
        );
      }
      if (url.includes("/api/billing/plan-diff")) {
        return route.fulfill(json({ from_plan: "pro", to_plan: "free_solo", lost_features: [{ feature_key: "designer", from: "true", to: "false" }] }));
      }
      if (url.includes("/api/billing/portal/stripe")) {
        return route.fulfill({ status: 400, contentType: "application/json", body: JSON.stringify({ detail: "No billing customer on file" }) });
      }
      return route.fulfill(
        json({
          workspace_id: "ws_e2e",
          plan_id: "pro",
          subscription_status: "active",
          features: { bulk_suite: "false" },
          extra_project_slots: 1,
          active_projects: 2,
          active_project_limit: 4,
          trial_ends_at: null,
          current_period_end: "2026-11-01T00:00:00Z",
        }),
      );
    });
    await page.goto("/settings/billing");
    await expect(page.getByTestId("billing-page")).toBeVisible({ timeout: 120_000 });
    await expect(page.getByTestId("billing-plan-price")).toContainText("$39");
    await expect(page.getByTestId("billing-charge")).toContainText("$54.00");
    await expect(page.getByRole("button", { name: "Manage billing" })).toBeVisible();
    await page.getByRole("button", { name: "Manage billing" }).click();
    await expect(page.getByTestId("billing-payment").getByTestId("billing-action-error")).toContainText(
      "No Stripe customer on file yet",
    );
  });
});
