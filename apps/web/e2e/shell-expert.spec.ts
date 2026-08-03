import { expect, test } from "@playwright/test";

test.describe("App shell & Expert (mocked API)", () => {
  test("tokens and kit harness pages render", async ({ page }) => {
    await page.goto("/e2e/tokens");
    await expect(page.getByTestId("tokens-page")).toBeVisible();
    await page.goto("/e2e/kit");
    await expect(page.getByTestId("kit-page")).toBeVisible();
  });

  test("expert panel opens from harness with mocked ask", async ({ page }) => {
    await page.route("**/api/expert/ask", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          answer_markdown: "XPath extends views without replacing arch [1].",
          citations: [
            {
              source: "odoo_docs",
              version: "19.0",
              breadcrumb: "Views",
              chunk_id: "c1",
            },
          ],
          grounded: true,
          declined: false,
          suggested_tools: [],
          caution_flags: [],
        }),
      });
    });

    await page.route("**/api/connections/**", async (route) => {
      const url = route.request().url();
      if (url.endsWith("/connections") || url.match(/\/api\/connections$/)) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            {
              id: "demo-conn",
              name: "Demo",
              url: "http://127.0.0.1:8069",
              db_name: "odoo",
              username: "admin",
              server_version: "19.0",
              created_at: null,
              updated_at: null,
              capabilities: {
                major: 19,
                edition: "community",
                server_version: "19.0",
                supported: ["view_inject_inherit", "base_automation_safe_triggers"],
                unsupported: [],
                ga: true,
                message: "ok",
              },
            },
          ]),
        });
        return;
      }
      if (url.includes("/demo-conn") && !url.includes("/models")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: "demo-conn",
            name: "Demo",
            url: "http://127.0.0.1:8069",
            db_name: "odoo",
            username: "admin",
            server_version: "19.0",
            created_at: null,
            updated_at: null,
            capabilities: {
              major: 19,
              edition: "community",
              server_version: "19.0",
              supported: ["view_inject_inherit", "base_automation_safe_triggers"],
              unsupported: [],
              ga: true,
              message: "ok",
            },
          }),
        });
        return;
      }
      await route.continue();
    });

    await page.goto("/connections/demo-conn/builder");
    await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 60_000 });
    await page.getByRole("button", { name: "Open Odoo Expert" }).click();
    await expect(page.getByTestId("expert-panel")).toBeVisible();
    await page.getByTestId("expert-input").fill("What is xpath inheritance?");
    await page.getByRole("button", { name: "Ask Expert" }).click();
    await expect(page.getByText("Grounded")).toBeVisible();
    await expect(page.getByText("XPath extends views")).toBeVisible();
  });

  test("command palette opens with keyboard shortcut", async ({ page }) => {
    await page.route("**/api/connections/**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "demo-conn",
            name: "Demo",
            url: "http://127.0.0.1:8069",
            db_name: "odoo",
            username: "admin",
            server_version: "19.0",
            created_at: null,
            updated_at: null,
          },
        ]),
      });
    });
    await page.route("**/api/connections/demo-conn", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "demo-conn",
          name: "Demo",
          url: "http://127.0.0.1:8069",
          db_name: "odoo",
          username: "admin",
          server_version: "19.0",
          created_at: null,
          updated_at: null,
          capabilities: { supported: [], unsupported: [], ga: true, edition: "community", message: "ok" },
        }),
      });
    });

    await page.goto("/connections/demo-conn");
    await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 60_000 });
    await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
    await expect(page.getByTestId("command-palette")).toBeVisible();
  });
});
