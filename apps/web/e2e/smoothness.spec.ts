import { test, expect, type Page } from "@playwright/test";

/**
 * Q2 touch 145: smoothness test. CPU throttled 4x (a mid-range laptop); a key interaction fails if it drops frames:
 * more than 10% of frames over 50 ms, or any single frame over 120 ms, while the interaction animates.
 */
const base = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3010";

async function measure(page: Page, act: () => Promise<void>, ms = 900) {
  await page.evaluate(() => {
    const w = window as unknown as { __frames: number[]; __stop: boolean };
    w.__frames = []; w.__stop = false;
    let last = performance.now();
    const tick = (t: number) => { w.__frames.push(t - last); last = t; if (!w.__stop) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  });
  await act();
  await page.waitForTimeout(ms);
  return page.evaluate(() => {
    const w = window as unknown as { __frames: number[]; __stop: boolean };
    w.__stop = true;
    const f = w.__frames.slice(1);
    return { n: f.length, slow: f.filter((x) => x > 50).length, worst: Math.max(0, ...f) };
  });
}

test.beforeEach(async ({ page }) => {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
});

const CASES: { name: string; path: string; act: (p: Page) => Promise<void> }[] = [
  { name: "theme switch", path: "/settings", act: async (p) => { await p.getByTestId("settings-theme").locator("select").selectOption("dark"); } },
  { name: "open approvals and scroll", path: "/approvals", act: async (p) => { await p.mouse.wheel(0, 800); } },
  { name: "connect page scroll", path: "/e2e/connect?state=empty", act: async (p) => { await p.mouse.wheel(0, 600); } },
];

for (const c of CASES) {
  test(`smooth: ${c.name}`, async ({ page }) => {
    await page.goto(`${base}${c.path}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(800);
    const r = await measure(page, () => c.act(page));
    expect(r.n, "frames sampled").toBeGreaterThan(10);
    expect(r.slow / r.n, `slow-frame share (worst ${Math.round(r.worst)} ms)`).toBeLessThanOrEqual(0.1);
    expect(r.worst).toBeLessThan(120);
  });
}
