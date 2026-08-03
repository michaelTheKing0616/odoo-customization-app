import { test, expect } from "@playwright/test";

test.describe("Pricing page (MON-4)", () => {
  test("renders tier comparison from registry", async ({ page }) => {
    await page.goto("/pricing");
    await expect(page.getByRole("heading", { name: "Pricing" })).toBeVisible();
    await expect(page.getByText("Free Solo")).toBeVisible();
    await expect(page.getByText("Pro")).toBeVisible();
    await expect(page.getByText("Project Pass")).toBeVisible();
    await expect(page.getByText("Operate tools")).toBeVisible();
  });

  test("landing links to pricing", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: "See pricing" })).toBeVisible();
  });
});
