import { test, expect, type Page } from "@playwright/test";

/**
 * Tope: /connect felt slow and froze, with the renderer near 113% CPU. This guards it: on /connect, idle for 30 s and
 * while typing, with 16,000 saved connections (what his account really had), there is no long task over 200 ms, React commits stay bounded, and nothing animates forever.
 */
const base = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3010";
const conns = Array.from({ length: 16000 }, (_, i) => ({ id: `c${i}`, name: `DB ${i}`, url: `https://db${i}.odoo.com`, db_name: `db${i}`, username: "a", server_version: "18.0", is_test_copy: i % 2 === 0, capabilities: null }));

async function probe(page: Page) {
  await page.addInitScript(() => {
    const w = window as unknown as Record<string, unknown>;
    const long: number[] = []; w.__long = long;
    try { new PerformanceObserver((l) => l.getEntries().forEach((e) => long.push(e.duration))).observe({ type: "longtask", buffered: true }); } catch { /* unsupported */ }
    let commits = 0; w.__commits = () => commits;
    // Count React commits through the devtools hook React looks for at startup.
    w.__REACT_DEVTOOLS_GLOBAL_HOOK__ = { supportsFiber: true, inject: () => 1, onCommitFiberRoot: () => { commits++; }, onCommitFiberUnmount: () => {}, onPostCommitFiberRoot: () => {}, checkDCE: () => {} };
    let muts = 0; w.__muts = () => muts;
    new MutationObserver((r) => { muts += r.length; }).observe(document, { subtree: true, childList: true, attributes: true, characterData: true });
  });
}
const read = (page: Page) => page.evaluate(() => {
  const w = window as unknown as { __long: number[]; __commits: () => number; __muts: () => number };
  const infinite = document.getAnimations().filter((a) => (a.effect?.getTiming().iterations ?? 1) === Infinity && a.playState === "running")
    .map((a) => { const t = (a.effect as KeyframeEffect | null)?.target as Element | null; return `${(a as CSSAnimation).animationName ?? "anim"} on ${t?.tagName}.${String(t?.className).slice(0, 30)}`; });
  return { long: [...w.__long], commits: w.__commits(), muts: w.__muts(), infinite };
});

test("connect stays quiet when idle and light while typing", async ({ page }) => {
  test.setTimeout(90_000);
  await page.route("**/api/**", (r) => {
    const u = new URL(r.request().url()).pathname;
    if (u === "/api/connections") return r.fulfill({ json: conns });
    return r.fulfill({ json: [] });
  });
  await probe(page);
  await page.goto(`${base}/connect`);
  await page.getByLabel("Label", { exact: true }).waitFor();
  await page.waitForTimeout(3000); // let the entrance settle
  const a = await read(page);
  await page.waitForTimeout(30_000);
  const b = await read(page);
  const idle = { commits: b.commits - a.commits, muts: b.muts - a.muts, long: b.long.slice(a.long.length) };
  console.log("IDLE", JSON.stringify(idle), "infinite:", JSON.stringify(b.infinite));
  const label = page.getByLabel("Label", { exact: true });
  await label.fill("");
  await label.pressSequentially("A second database for testing", { delay: 40 });
  const c = await read(page);
  const typing = { commits: c.commits - b.commits, long: c.long.slice(b.long.length) };
  console.log("TYPING", JSON.stringify(typing));
  expect(Math.max(0, ...idle.long), "longest idle task (ms)").toBeLessThan(200);
  expect(Math.max(0, ...typing.long), "longest task while typing (ms)").toBeLessThan(200);
  expect(idle.commits, "React commits in 30 s idle").toBeLessThanOrEqual(10);
  expect(idle.muts, "DOM mutations in 30 s idle").toBeLessThanOrEqual(200);
  expect(b.infinite, "endless animations").toEqual([]);
  // Root cause was rendering every saved connection (295,000 DOM nodes). The list now shows 50 at a time.
  expect(await page.locator('[data-testid^="connect-row-"]').count()).toBeLessThanOrEqual(50);
  expect(await page.evaluate(() => document.querySelectorAll("*").length), "DOM nodes on /connect").toBeLessThan(5000);
  await page.getByTestId("connect-saved-search").fill("DB 15999");
  await expect(page.getByTestId("connect-row-c15999")).toBeVisible();
});
