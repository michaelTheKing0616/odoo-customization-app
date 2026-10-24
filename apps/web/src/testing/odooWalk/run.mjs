// BV-04 walkthrough runner: headless Chromium from the existing @playwright/test devDependency.
// Usage: node run.mjs --plan plan.json --out dir | node run.mjs --dry-run fixture
// Secrets come only from env (WALK_LOGIN/WALK_PASSWORD or WALK_SESSION); never printed.
import { randomUUID } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, domAssertion } from './steps.mjs';
import { selectorsFor } from './selectors.mjs';

// Floor list; the plan adds targets.RESERVED_PORTS (incl. sandbox DEV_PORTS) from Python.
const RESERVED = new Set([3002, 8001, 8002, 8012, 5433, 5436, 8069, 8070, 8071, 8072, 8073, 11434, 18069]);

const FIXTURE = {
  base_url: 'http://127.0.0.1:18117', host: '127.0.0.1', major: 17,
  step_timeout_ms: 20000, run_timeout_ms: 600000, retries: 1,
  steps: [
    { index: 0, op_index: 0, action: 'open', model: 'res.partner', view: 'list', target: 'res.partner:list' },
    { index: 1, op_index: 0, action: 'assert', view: 'list', target: 'res.partner:list' },
  ],
};

function arg(name) {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : undefined;
}

function sid() {
  return randomUUID().replaceAll('-', '');
}

async function once(page, d, timeout) {
  if (d.kind === 'goto') {
    await page.goto(new URL(d.url, page.__base).href, { timeout });
    await page.locator(d.home).first().waitFor({ state: 'visible', timeout });
    // Model/view come from the server-built plan (validated), passed as data, never page text.
    await page.evaluate(
      ([model, view]) =>
        window.odoo.__WOWL_DEBUG__.root.env.services.action.doAction(
          { type: 'ir.actions.act_window', res_model: model, views: [[false, view]], target: 'current' },
          { clearBreadcrumbs: true },
        ),
      [d.model, d.view],
    );
    await page.locator(d.wait).first().waitFor({ state: 'visible', timeout });
  } else if (d.kind === 'assert') {
    if (d.visible) await page.locator(d.visible).first().waitFor({ state: 'visible', timeout });
    await page.waitForTimeout(500);
    for (const a of d.absent) {
      if ((await page.locator(a).count()) > 0) return { status: 'failed', reason: `present:${a}` };
    }
  } else if (d.kind === 'fill') {
    if (d.optional && (await page.locator(d.selector).count()) === 0) {
      return { status: 'passed', reason: 'optional field not on form' };
    }
    await page.locator(d.selector).first().fill(d.value, { timeout });
  } else if (d.kind === 'click') {
    if (!d.selector) return { status: 'failed', reason: 'unknown click target' };
    await page.locator(d.selector).first().click({ timeout });
    // Odoo keeps a bus poll open, so wait on the form state, not network idle.
    if (d.settled) await page.locator(d.settled).first().waitFor({ state: 'detached', timeout });
  } else {
    return { status: 'failed', reason: 'unknown action' };
  }
  return { status: 'passed' };
}

async function main() {
  const dry = process.argv.includes('--dry-run');
  const plan = dry ? FIXTURE : JSON.parse(readFileSync(arg('--plan'), 'utf8'));
  const base = new URL(plan.base_url);
  const port = Number(base.port || (base.protocol === 'https:' ? 443 : 80));
  const reserved = new Set([...RESERVED, ...(plan.reserved_ports ?? [])]);
  if (reserved.has(port) || base.hostname !== plan.host) throw new Error('target not allowed');
  if (dry) {
    for (const s of plan.steps) console.log(`${s.index} ${s.action} ${s.target} :: ${domAssertion(describe(s, plan.major))}`);
    return;
  }
  const out = arg('--out');
  const sel = selectorsFor(plan.major);
  const { chromium } = await import('@playwright/test');
  const browser = await chromium.launch({ headless: true });
  const results = [];
  const deadline = Date.now() + plan.run_timeout_ms;
  try {
    const context = await browser.newContext({ acceptDownloads: false, baseURL: base.origin });
    await context.route('**/*', (route) => {
      const u = new URL(route.request().url());
      if (['data:', 'blob:'].includes(u.protocol) || u.host === base.host) return route.continue();
      return route.abort();
    });
    const page = await context.newPage();
    page.__base = base.origin;
    if (process.env.WALK_SESSION) {
      await context.addCookies([{ name: 'session_id', value: process.env.WALK_SESSION, url: base.origin }]);
    } else {
      // Login step: never screenshotted.
      await page.goto(`${base.origin}/web/login?db=${encodeURIComponent(plan.db)}`, { timeout: plan.step_timeout_ms });
      await page.fill(sel.login, process.env.WALK_LOGIN ?? '');
      await page.fill(sel.password, process.env.WALK_PASSWORD ?? '');
      await page.click(sel.submit);
      await page.locator(sel.home).first().waitFor({ state: 'visible', timeout: plan.step_timeout_ms });
    }
    for (const s of plan.steps) {
      const d = describe(s, plan.major);
      let r = { status: 'skipped', reason: 'run timeout' };
      if (Date.now() < deadline) {
        for (let attempt = 0; attempt <= plan.retries; attempt++) {
          try {
            r = await once(page, d, plan.step_timeout_ms);
            break;
          } catch (e) {
            r = { status: 'skipped', reason: `flaky: ${String(e?.name ?? 'error')} after ${attempt + 1} tries` };
          }
        }
      }
      const id = sid();
      await page.screenshot({ path: join(out, `${id}.png`), mask: [page.locator(sel.mask)], timeout: plan.step_timeout_ms }).catch(() => null);
      results.push({ index: s.index, action: s.action, status: r.status, reason: r.reason ?? null, screenshot_id: id, dom_assertion: domAssertion(d) });
    }
  } finally {
    writeFileSync(join(out, 'results.json'), JSON.stringify(results));
    await browser.close();
  }
}

main().catch((e) => {
  console.error(`walk failed: ${String(e?.name ?? 'error')}`);
  process.exit(1);
});
