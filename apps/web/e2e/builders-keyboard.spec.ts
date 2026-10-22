import { expect, test, type Page } from "@playwright/test";

/**
 * SPEC 11 acceptance: keyboard-only walkthrough of View Designer on a live disposable Odoo.
 * Needs VD_CONN (a connection id on the API the web server proxies to). No mouse anywhere.
 */
const conn = process.env.VD_CONN;

async function tabUntil(page: Page, ok: () => Promise<boolean>, max = 120, key: "Tab" | "Shift+Tab" = "Tab"): Promise<void> {
  for (let i = 0; i < max; i++) {
    if (await ok()) return;
    await page.keyboard.press(key);
  }
  throw new Error("Tab never reached the target");
}

const focused = (page: Page) =>
  page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null;
    return { role: el?.getAttribute("role") ?? "", testid: el?.getAttribute("data-testid") ?? "", text: el?.textContent ?? "" };
  });

test.describe("Builders keyboard-only walkthrough", () => {
  test.skip(!conn, "set VD_CONN to a connection on a disposable database");

  test("tree, move, announce, undo, command bar, publish: keyboard only", async ({ page }) => {
    test.setTimeout(180_000);
    await page.goto(`/connections/${conn}/view-designer?model=sale.order&type=form`);
    await expect(page.getByRole("tree", { name: "Screen layers" })).toBeVisible({ timeout: 90_000 });

    // 1. Reach the layers tree with Tab only.
    await tabUntil(page, async () => (await focused(page)).role === "treeitem");

    // 2. Arrow through the tree; Alt+Arrow moves an item and the live region says what happened.
    const live = page.getByTestId("vd-live");
    let moved = false;
    for (let i = 0; i < 40 && !moved; i++) {
      await page.keyboard.press("ArrowDown");
      await page.keyboard.press("Alt+ArrowDown");
      moved = /^Moved /i.test(((await live.textContent()) ?? "").trim());
    }
    expect(moved, "an item moved with Alt+ArrowDown and was announced").toBe(true);
    await expect(page.getByTestId("vd-publish")).toContainText(/Publish changes \(1\)/);

    // 3. Undo from the keyboard.
    await page.keyboard.press("Control+z");
    await expect(page.getByTestId("vd-publish")).toHaveText(/^Publish changes$/);

    // 4. Command bar: opens with Ctrl+K, traps focus, Escape closes and focus goes back.
    const before = await focused(page);
    await page.keyboard.press("Control+k");
    const bar = page.getByRole("dialog", { name: "Command bar" });
    await expect(bar).toBeVisible();
    await expect(bar).toHaveAttribute("aria-modal", "true");
    for (let i = 0; i < 6; i++) await page.keyboard.press("Tab");
    expect(await page.evaluate(() => Boolean(document.activeElement?.closest('[role="dialog"]')))).toBe(true);
    await page.keyboard.press("Escape");
    await expect(bar).toBeHidden();
    expect((await focused(page)).role).toBe(before.role);

    // 5. Move again and publish without the mouse.
    await page.keyboard.press("Alt+ArrowDown"); // the same move that worked above (undo put it back)
    await expect(page.getByTestId("vd-publish")).toContainText(/Publish changes \(1\)/);
    // Publish sits in the top bar, before the tree, so walk back to it.
    await tabUntil(page, async () => (await focused(page)).testid === "vd-publish", 200, "Shift+Tab");
    await page.keyboard.press("Enter");
    await expect(page.getByText("Published", { exact: true })).toBeVisible({ timeout: 60_000 });
  });
});
