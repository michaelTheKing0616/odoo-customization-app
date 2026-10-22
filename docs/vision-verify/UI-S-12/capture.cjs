// UI-S-12 vision capture: node capture.cjs <baseUrl> <outDir> <prefix>
// Run with NODE_PATH=apps/web/node_modules so @playwright/test resolves.
// Shots:
//   - form + kanban at desktop 1440x900 and narrow 390x844, list desktop
//   - the three canvas states (xml-invalid, inherit-conflict, preview-stale)
//   - mid-drag form shot (ReorderableBlocks pointer reorder + basalt ghost)
//   - keyboard move (ArrowDown on the selected field)
//   - Properties inspector (harness) and the premium harness inspector
//   - Advanced structure canvas (/e2e/designer-structure) form, list, kanban, search
//   - dark theme form
// The Next dev indicator is hidden so it never sits on top of the canvas.
const { chromium } = require("@playwright/test");
const path = require("path");

const [, , base = "http://127.0.0.1:3002", outDir = ".", prefix = "after"] = process.argv;
const HIDE_DEV = "nextjs-portal{display:none!important}";
const viewports = [
  { name: "desktop", width: 1440, height: 900, isMobile: false },
  { name: "narrow", width: 390, height: 844, isMobile: true },
];
const modes = [
  { mode: "form", testId: "designer-form-layout" },
  { mode: "kanban", testId: "designer-kanban-layout" },
  { mode: "list", testId: "designer-list-layout" },
];

async function open(page, url, waitFor) {
  await page.goto(url, { waitUntil: "networkidle", timeout: 120000 });
  await page.addStyleTag({ content: HIDE_DEV });
  if (waitFor) await page.getByTestId(waitFor).first().waitFor({ timeout: 60000 });
  await page.waitForTimeout(400);
}

async function shot(page, name, opts = {}) {
  const file = path.join(outDir, `${prefix}-${name}.png`);
  await page.screenshot({ path: file, animations: "disabled", ...opts });
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  console.log(`${file} overflowX=${overflow}`);
}

(async () => {
  const browser = await chromium.launch();
  for (const vp of viewports) {
    const ctx = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      deviceScaleFactor: 2,
      isMobile: vp.isMobile,
      hasTouch: vp.isMobile,
    });
    const page = await ctx.newPage();
    for (const { mode, testId } of modes) {
      if (vp.name === "narrow" && mode === "list") continue;
      await open(page, `${base}/e2e/designer?mode=${mode}`, testId);
      await shot(page, `${mode}-${vp.name}`, { fullPage: vp.name === "narrow" });
    }
    if (vp.name === "desktop") {
      for (const state of ["xml-invalid", "inherit-conflict", "preview-stale"]) {
        await open(page, `${base}/e2e/designer?mode=form&state=${state}`, "designer-canvas-state");
        await shot(page, `state-${state}-desktop`);
      }
      // Mid-drag: lift a row through ReorderableBlocks pointer reorder.
      await open(page, `${base}/e2e/designer?mode=form`, "canvas-field-x_partner_id");
      const row = page.getByTestId("canvas-field-x_partner_id");
      await row.hover();
      const box = await row.getByTestId("canvas-grip").boundingBox();
      if (box) {
        await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
        await page.mouse.down();
        await page.mouse.move(box.x + box.width / 2 + 6, box.y + box.height / 2 + 12, { steps: 3 });
        await page.mouse.move(box.x + box.width / 2 + 24, box.y + box.height / 2 + 34, { steps: 6 });
        await page.waitForTimeout(150);
        await shot(page, "form-drag-desktop");
        await page.mouse.up();
      }
      // Keyboard move: select Name, press ArrowDown (designer-keyboard.spec path).
      await open(page, `${base}/e2e/designer?mode=form`, "form-canvas");
      await page.getByRole("button", { name: /Name.*x_name/ }).first().click();
      await page.keyboard.press("ArrowDown");
      await page.waitForTimeout(200);
      await shot(page, "form-keyboard-desktop");
      // Inspector: select a field, Properties tab opens.
      await open(page, `${base}/e2e/designer?mode=form`, "form-canvas");
      await page.getByRole("button", { name: /Customer.*x_partner_id/ }).first().click();
      await page.waitForTimeout(400);
      await shot(page, "form-inspector-desktop");
      // Premium harness: real DesignerFieldInspector in the basalt rail.
      await open(page, `${base}/e2e/designer-premium`, "designer-premium-studio");
      await shot(page, "premium-desktop");
      // Advanced structure canvas.
      for (const view of ["form", "list", "kanban", "search"]) {
        await open(page, `${base}/e2e/designer-structure?view=${view}`, "designer-structure-editor");
        await shot(page, `structure-${view}-desktop`, { fullPage: true });
      }
    }
    await ctx.close();
  }
  // Dark theme form (html.dark on the app).
  const dark = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
    colorScheme: "dark",
  });
  const dpage = await dark.newPage();
  await dpage.addInitScript(() => {
    try {
      localStorage.setItem("theme", "dark");
    } catch {}
    document.addEventListener("DOMContentLoaded", () => document.documentElement.classList.add("dark"));
  });
  await open(dpage, `${base}/e2e/designer?mode=form`, "designer-form-layout");
  await dpage.evaluate(() => document.documentElement.classList.add("dark"));
  await dpage.waitForTimeout(300);
  await shot(dpage, "form-dark-desktop");
  await dark.close();
  await browser.close();
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
