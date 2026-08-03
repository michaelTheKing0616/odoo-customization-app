import { expect, test } from "@playwright/test";

test.describe("Designer EE view panels (REM-8)", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/connections/e2e-ee-connection/views/preview", async (route) => {
      const body = route.request().postDataJSON() as {
        view_type: string;
        spec: Record<string, unknown>;
      };
      const { view_type, spec } = body;
      let arch = `<${view_type} string="${spec.string ?? "View"}"/>`;
      if (view_type === "map" && spec.routing) {
        arch = `<map string="Map" res_partner="${spec.res_partner}" routing="1"/>`;
      }
      if (view_type === "map" && Array.isArray(spec.fields) && spec.fields.length) {
        const names = spec.fields.map((f: { name?: string }) => f.name).filter(Boolean).join(",");
        arch = arch.replace("/>", ` marker_popup_fields="${names}"/>`);
      }
      if (view_type === "gantt") {
        arch = `<gantt date_start="${spec.date_start}" default_scale="${spec.default_scale}"${
          spec.dependency_field ? ` dependency_field="${spec.dependency_field}"` : ""
        }${spec.progress ? ` progress="${spec.progress}"` : ""}/>`;
      }
      if (view_type === "grid") {
        arch = `<grid row_field="${spec.row_field}" col_field="${spec.col_field}" measure="${spec.measure}" adjustment="${spec.adjustment}"/>`;
      }
      if (view_type === "cohort") {
        arch = `<cohort date_start="${spec.date_start}" mode="${spec.mode}"/>`;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ arch }),
      });
    });
  });

  test("map routing toggle emits routing attr", async ({ page }) => {
    await page.goto("/e2e/designer-ee");
    await expect(page.getByTestId("ee-map-panel")).toBeVisible();
    await page.getByTestId("designer-map-routing").check();
    await page.getByTestId("ee-preview-refresh").click();
    await expect(page.getByTestId("ee-arch-preview")).toContainText('routing="1"');
  });

  test("map marker fields list updates arch", async ({ page }) => {
    await page.goto("/e2e/designer-ee");
    await expect(page.getByTestId("ee-map-panel")).toBeVisible();
    await page.getByTestId("designer-map-field-progress").check();
    await page.getByTestId("ee-preview-refresh").click();
    await expect(page.getByTestId("ee-arch-preview")).toContainText('marker_popup_fields="amount,progress"');
  });

  test("gantt progress control emits progress attr", async ({ page }) => {
    await page.goto("/e2e/designer-ee");
    await page.getByTestId("ee-view-type").selectOption("gantt");
    await page.getByTestId("designer-gantt-progress").selectOption("progress");
    await page.getByTestId("ee-preview-refresh").click();
    await expect(page.getByTestId("ee-arch-preview")).toContainText('progress="progress"');
  });

  test("gantt default_scale and dependency_field in arch", async ({ page }) => {
    await page.goto("/e2e/designer-ee");
    await page.getByTestId("ee-view-type").selectOption("gantt");
    await expect(page.getByTestId("ee-gantt-panel")).toBeVisible();
    await page.getByTestId("designer-gantt-default-scale").selectOption("month");
    await page.getByTestId("designer-gantt-dependency").selectOption("depend_on_ids");
    await page.getByTestId("ee-preview-refresh").click();
    const arch = page.getByTestId("ee-arch-preview");
    await expect(arch).toContainText('default_scale="month"');
    await expect(arch).toContainText('dependency_field="depend_on_ids"');
  });

  test("grid panel gated on community edition", async ({ page }) => {
    await page.goto("/e2e/designer-ee");
    await page.getByTestId("ee-edition-select").selectOption("community");
    await page.getByTestId("ee-view-type").selectOption("grid");
    await expect(page.getByTestId("ee-grid-panel")).not.toBeVisible();
    await page.getByTestId("ee-edition-select").selectOption("enterprise");
    await page.getByTestId("ee-view-type").selectOption("grid");
    await expect(page.getByTestId("ee-grid-panel")).toBeVisible();
    await page.getByTestId("designer-grid-adjustment").selectOption("value");
    await page.getByTestId("ee-preview-refresh").click();
    await expect(page.getByTestId("ee-arch-preview")).toContainText('adjustment="value"');
  });

  test("cohort mode emits mode attr", async ({ page }) => {
    await page.goto("/e2e/designer-ee");
    await page.getByTestId("ee-view-type").selectOption("cohort");
    await page.getByTestId("designer-cohort-mode").selectOption("churn");
    await page.getByTestId("ee-preview-refresh").click();
    await expect(page.getByTestId("ee-arch-preview")).toContainText('mode="churn"');
  });
});
