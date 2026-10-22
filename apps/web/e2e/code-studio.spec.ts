import { expect, test, type Page } from "@playwright/test";

test.describe("Code Studio page", () => {
  test("renders editor when gate allows or shows gating callout", async ({ page }) => {
    await page.goto("/connect");
    const firstLink = page.locator('[data-testid^="nav-"]').first();
    if ((await firstLink.count()) === 0) {
      test.skip();
    }
    const connectionLink = page.locator('a[href^="/connections/"]').first();
    if ((await connectionLink.count()) === 0) {
      test.skip();
    }
    const href = await connectionLink.getAttribute("href");
    if (!href) test.skip();
    await page.goto(`${href}/code-studio`);
    await expect(page.getByTestId("code-studio-page")).toBeVisible();
    const editor = page.getByTestId("code-studio-editor");
    const gating = page.getByTestId("gating-callout");
    await expect(editor.or(gating)).toBeVisible();
  });
});

/** UI-S-18 harness: the real screen with the API mocked in the browser. */
async function mockCodeStudioApi(page: Page, { supported = true }: { supported?: boolean } = {}) {
  await page.route("**/api/**", async (route) => {
    const url = route.request().url();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (/\/api\/connections\/demo-conn(\?|$)/.test(url)) {
      return json({
        id: "demo-conn",
        name: "Lagos Sessions",
        url: "http://127.0.0.1:8069",
        db_name: "odoo",
        username: "admin",
        server_version: "19.0",
        write_mode: "standard",
        created_at: null,
        updated_at: null,
      });
    }
    if (/production-readiness/.test(url)) return json({ passed: true, items: [], first_write_acknowledged: true });
    if (/code-studio\/gate/.test(url)) {
      return json({
        probe: { supported },
        gating: {
          feature: "code_studio",
          title: supported ? "Live code server actions" : "Live code actions unavailable",
          why: supported
            ? "This instance accepts state=code server actions via RPC."
            : "Live code actions are not available on this instance.",
          options: supported ? [] : ["Export Python as an installable module (Option A)"],
          available: supported,
          capability_key: "code_server_actions",
          gating_choices: [],
        },
        developer_role_required: true,
        entitlement_key: "dev_tools",
      });
    }
    if (/code-studio\/context/.test(url)) {
      return json({ major: 19, symbols: [{ name: "records", description: "Recordset the action runs on." }] });
    }
    if (/code-studio\/snippets/.test(url)) return json({ snippets: [] });
    if (/code-studio\/validate/.test(url)) {
      return json({ ok: true, syntax_ok: true, warnings: [], error: null, line: null });
    }
    if (/code-studio\/bind/.test(url)) return json({ detail: "bind must not be called here" }, 500);
    if (/\/models/.test(url)) {
      return json([{ id: 1, model: "res.partner", name: "Contact", state: "base", transient: false }]);
    }
    return json([]);
  });
}

test.describe("Code Studio authoring gate (UI-S-18 harness)", () => {
  test("Validate is the primary, and live bind waits for it", async ({ page }) => {
    await mockCodeStudioApi(page);
    await page.goto("/e2e/code-studio");
    await expect(page.getByTestId("code-studio-page")).toBeVisible();
    await expect(page.getByTestId("code-studio-option-a-warning")).toContainText("Never installs from here");

    const bind = page.getByRole("button", { name: "Bind live action" });
    await expect(bind).toBeDisabled();
    await expect(page.getByTestId("code-studio-bind-block")).toHaveText("Validate this code first.");

    await page.getByRole("button", { name: "Validate code" }).click();
    await expect(page.getByTestId("code-studio-gate-pill")).toHaveText("Validated");
    await expect(bind).toBeEnabled();

    await page.getByLabel("Line 2", { exact: true }).fill("    rec.write({})");
    await expect(page.getByTestId("code-studio-stale")).toContainText("This code changed. Validate again.");
    await expect(bind).toBeDisabled();
  });

  test("a refused probe opens the Option A path with no live bind", async ({ page }) => {
    await mockCodeStudioApi(page, { supported: false });
    await page.goto("/e2e/code-studio");
    await expect(page.getByTestId("gating-callout")).toBeVisible();
    await expect(page.getByRole("radio", { name: "Option A module" })).toBeChecked();
    await expect(page.getByRole("button", { name: "Bind live action" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Download module zip" })).toBeDisabled();
  });
});
