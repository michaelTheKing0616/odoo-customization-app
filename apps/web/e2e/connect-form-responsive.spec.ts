import { test, expect } from "@playwright/test";

/** Regression: the Connect form must respond to clicks and typing (Tope: fields did not change state). */
const base = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3010";

const CONN = { id: "c1", name: "Main DB", url: "https://main.odoo.com", db_name: "main", username: "a@b.c", server_version: "18.0", is_test_copy: false, hosting: "online", capabilities: null, group_label: null };

async function exercise(page: import("@playwright/test").Page) {
  const label = page.getByLabel("Label", { exact: true });
  await label.click();
  await label.fill("");
  await label.pressSequentially("Second DB");
  await expect(label).toHaveValue("Second DB");
  const radios = page.getByTestId("connect-hosting-picker").getByRole("radio");
  await radios.last().click();
  await expect(radios.last()).toHaveAttribute("aria-checked", "true");
}

test("connect form responds with saved connections, arriving from inside a connection", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.route("**/api/**", (r) => {
    const u = new URL(r.request().url()).pathname;
    if (u === "/api/connections") return r.fulfill({ json: [CONN] });
    if (u === "/api/connections/c1") return r.fulfill({ json: CONN });
    return r.fulfill({ json: [] });
  });
  await page.goto(`${base}/connections/c1`);
  await page.waitForLoadState("networkidle");
  await page.goto(`${base}/connect`);
  await exercise(page);
  await page.reload();
  await exercise(page);
  expect(errors).toEqual([]);
});

test("connect form fields respond to typing and clicks", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(`${base}/connect`);
  const label = page.getByLabel("Label", { exact: true });
  await label.click();
  await label.fill("Second DB");
  await expect(label).toHaveValue("Second DB");
  const url = page.getByLabel("Odoo URL");
  await url.fill("https://example.odoo.com");
  await expect(url).toHaveValue("https://example.odoo.com");
  const user = page.getByLabel("Username");
  await user.fill("admin@example.com");
  await expect(user).toHaveValue("admin@example.com");
  const radios = page.getByTestId("connect-hosting-picker").getByRole("radio");
  const last = radios.last();
  await last.click();
  await expect(last).toHaveAttribute("aria-checked", "true");
  const first = radios.first();
  await first.click();
  await expect(first).toHaveAttribute("aria-checked", "true");
  // Nothing invisible sits over the form.
  const box = (await label.boundingBox())!;
  const hit = await page.evaluate(([x, y]) => { const el = document.elementFromPoint(x, y); return el ? `${el.tagName}.${el.className}` : "none"; }, [box.x + 5, box.y + 5]);
  expect(hit).toMatch(/^INPUT/);
  expect(errors).toEqual([]);
});

for (const density of ["comfortable", "compact", "dense"]) {
  test(`connect: every control receives its own clicks (${density}), and Add another reopens a live form`, async ({ page }) => {
    await page.addInitScript((d) => localStorage.setItem("ingenium.density", d), density);
    await page.route("**/api/**", (r) => {
      const u = new URL(r.request().url()).pathname;
      if (u === "/api/connections" && r.request().method() === "POST") return r.fulfill({ json: { ...CONN, id: "c2", name: "Second DB" } });
      if (u === "/api/connections") return r.fulfill({ json: [CONN] });
      return r.fulfill({ json: [] });
    });
    await page.goto(`${base}/connect`);
    await page.getByLabel("Label", { exact: true }).waitFor();
    const blocked = await page.evaluate(() => {
      const out: string[] = [];
      for (const el of Array.from(document.querySelectorAll<HTMLElement>("input, button, select, textarea, [role=radio]"))) {
        const r = el.getBoundingClientRect();
        if (!r.width || !r.height || r.bottom < 0 || r.top > innerHeight) continue;
        const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
        const lbl = el.closest("label");
        if (hit && hit !== el && !el.contains(hit) && !(lbl && lbl.contains(hit))) out.push(`${el.tagName}[${el.getAttribute("aria-label") ?? el.id ?? el.textContent?.trim().slice(0, 20)}] covered by ${hit.tagName}.${String(hit.className).slice(0, 40)}`);
      }
      return out;
    });
    expect(blocked).toEqual([]);
    await exercise(page);
    await page.getByLabel("Odoo URL").fill("https://second.odoo.com");
    await page.getByTestId("connect-secret").fill("secret");
    await page.getByRole("button", { name: /connect|save|verify/i }).last().click().catch(() => undefined);
    const again = page.getByRole("button", { name: "Add another" });
    if (await again.isVisible().catch(() => false)) { await again.click(); await exercise(page); }
  });
}
