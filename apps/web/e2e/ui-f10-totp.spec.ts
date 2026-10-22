import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import path from "node:path";

const SHOTS = path.resolve(__dirname, "../../../docs/vision-verify/UI-F10");

async function pasteCode(page: Page, text: string) {
  const input = page.getByLabel("Two-factor code");
  await input.focus();
  await input.evaluate((el, value) => {
    const data = new DataTransfer();
    data.setData("text/plain", value);
    el.dispatchEvent(new ClipboardEvent("paste", { clipboardData: data, bubbles: true, cancelable: true }));
  }, text);
}

async function expectNoSeriousAxeViolations(page: Page, label: string) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const serious = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical",
  );
  expect(serious, `${label} axe violations: ${JSON.stringify(serious, null, 2)}`).toEqual([]);
}

test.describe("UI-F10 TOTP input", () => {
  test("password login: paste fills all slots, one-time-code autocomplete, axe clean", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/login");
    const input = page.getByLabel("Two-factor code");
    await expect(input).toHaveAttribute("autocomplete", "one-time-code");
    await expect(input).toHaveAttribute("inputmode", "numeric");
    await pasteCode(page, "123 456");
    await expect(input).toHaveValue("123456");
    await expect(page.locator("[data-slot='totp-slot']")).toHaveText(["1", "2", "3", "4", "5", "6"]);
    await expectNoSeriousAxeViolations(page, "/login");
    await page.screenshot({ path: `${SHOTS}/login-desktop.png`, fullPage: true });
  });

  test("password login at 390px: axe clean", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/login");
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
    await expectNoSeriousAxeViolations(page, "/login 390");
    await page.screenshot({ path: `${SHOTS}/login-390.png`, fullPage: true });
  });

  test("partial code shows the inline error", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/login");
    await page.getByLabel("Email").fill("ops@example.com");
    await page.getByLabel("Password").fill("not-a-real-password");
    await page.getByLabel("Two-factor code").pressSequentially("123");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "Enter all 6 digits" })).toBeVisible();
    await expectNoSeriousAxeViolations(page, "/login error");
    await page.screenshot({ path: `${SHOTS}/login-error-desktop.png`, fullPage: true });
  });

  test("OAuth step at 390px: submit enables on 6 digits, axe clean", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/login?oauth_totp=1&token=e2e-token");
    const submit = page.getByRole("button", { name: "Complete sign-in" });
    await expect(submit).toBeDisabled();
    await expect(page.getByLabel("Two-factor code")).toBeFocused();
    await page.keyboard.type("12ab34");
    await expect(page.getByLabel("Two-factor code")).toHaveValue("1234");
    await page.keyboard.type("56");
    await expect(submit).toBeEnabled();
    await expectNoSeriousAxeViolations(page, "/login oauth");
    await page.screenshot({ path: `${SHOTS}/login-oauth-390.png`, fullPage: true });
  });
});
