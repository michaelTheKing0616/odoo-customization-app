import { expect, test } from "@playwright/test";
import path from "node:path";

const OUT_DIR = path.resolve(__dirname, "../../../docs/vision-verify");

const PRIMARY_ARCH =
  '<form><sheet><group><field name="name"/><field name="email"/></group></sheet></form>';

test.describe("Overlay editor UI loop", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/connections/e2e-connection/views/**", async (route) => {
      const url = route.request().url();
      if (url.includes("/primary")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: 1,
            name: "res.partner.form",
            model: "res.partner",
            type: "form",
            arch: PRIMARY_ARCH,
          }),
        });
        return;
      }
      if (url.includes("/resolve-field")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            field_name: "email",
            candidates: [{ xpath: "//field[@name='email']", match: '<field name="email"/>' }],
            ambiguous: false,
          }),
        });
        return;
      }
      if (url.includes("/overlay/preview")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            xpath_arch:
              '<data>\n  <xpath expr="//field[@name=\'email\']" position="attributes">\n    <attribute name="invisible">1</attribute>\n  </xpath>\n</data>',
            issues: [],
          }),
        });
        return;
      }
      if (url.includes("/overlay/apply")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            xpath_arch:
              '<data>\n  <xpath expr="//field[@name=\'email\']" position="attributes">\n    <attribute name="invisible">1</attribute>\n  </xpath>\n</data>',
            issues: [],
            view_id: 42,
            snapshot_id: "snap-overlay-1",
            inherit_name: "res.partner.overlay.form",
          }),
        });
        return;
      }
      await route.continue();
    });
  });

  test("select hide save shows xpath peek", async ({ page }) => {
    await page.goto("/e2e/overlay");
    await expect(page.getByTestId("overlay-harness")).toBeVisible();
    await page.getByTestId("pick-email").click();
    await expect(page.getByTestId("overlay-selected")).toContainText("email");
    await expect(page.getByTestId("overlay-xpath-peek")).toBeVisible();
    await expect(page.getByTestId("overlay-xpath-peek")).toContainText("invisible");
    await page.getByTestId("overlay-save").click();
    await expect(page.getByText(/Saved inherit/)).toBeVisible();
    await page.screenshot({
      path: path.join(OUT_DIR, "overlay-editor.png"),
      fullPage: true,
    });
  });
});

test.describe("Overlay live loop (docker Odoo)", () => {
  test.skip(!process.env.ODOO_E2E, "Set ODOO_E2E=1 with docker Odoo + connection env");

  test("hide field on res.partner through API overlay loop", async ({ page, request }) => {
    const connectionId = process.env.ODOO_E2E_CONNECTION_ID;
    test.skip(!connectionId, "ODOO_E2E_CONNECTION_ID required");
    const apiBase = process.env.PLAYWRIGHT_API_BASE || "http://127.0.0.1:8000";

    const primary = await request.get(
      `${apiBase}/api/connections/${connectionId}/views/res.partner/form/primary`,
    );
    expect(primary.ok()).toBeTruthy();
    const primaryBody = await primary.json();
    const beforeArch: string = primaryBody.arch || "";
    expect(beforeArch).toContain('name="email"');

    const preview = await request.post(
      `${apiBase}/api/connections/${connectionId}/views/res.partner/form/overlay/preview`,
      {
        data: {
          model: "res.partner",
          view_type: "form",
          operation: "hide",
          field_name: "email",
          xpath: "//field[@name='email']",
        },
      },
    );
    expect(preview.ok()).toBeTruthy();

    const apply = await request.post(
      `${apiBase}/api/connections/${connectionId}/views/res.partner/form/overlay/apply`,
      {
        data: {
          model: "res.partner",
          view_type: "form",
          operation: "hide",
          field_name: "email",
          xpath: "//field[@name='email']",
        },
      },
    );
    expect(apply.ok()).toBeTruthy();
    const applyBody = await apply.json();
    expect(applyBody.xpath_arch).toContain("invisible");

    const afterPrimary = await request.get(
      `${apiBase}/api/connections/${connectionId}/views/res.partner/form/primary`,
    );
    const afterBody = await afterPrimary.json();
    const mergedArch: string = afterBody.arch || "";
    expect(mergedArch).not.toEqual(beforeArch);

    if (applyBody.snapshot_id) {
      const restore = await request.post(
        `${apiBase}/api/connections/${connectionId}/snapshots/${applyBody.snapshot_id}/restore`,
      );
      expect(restore.ok()).toBeTruthy();
    }

    await page.goto(`/connections/${connectionId}/designer?model=res.partner`);
    await page.screenshot({
      path: path.join(OUT_DIR, "overlay-editor-live.png"),
      fullPage: true,
    });
  });
});
