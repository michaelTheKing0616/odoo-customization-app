import { expect, test } from "@playwright/test";

test.describe("Automation action caps (mock Odoo 16)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/e2e/automation-caps");
    await expect(page.getByTestId("harness-profile")).toHaveValue("odoo16");
    await expect(page.getByTestId("harness-major")).toHaveText(/16/);
  });

  test("greys out update_field and related_write options", async ({ page }) => {
    const select = page.getByTestId("automation-action-kind");
    await expect(select).toBeVisible();

    const updateField = select.locator('option[value="update_field"]');
    const relatedWrite = select.locator('option[value="related_write"]');
    const createActivity = select.locator('option[value="create_activity"]');

    await expect(updateField).toHaveAttribute("disabled", "");
    await expect(relatedWrite).toHaveAttribute("disabled", "");
    await expect(createActivity).not.toHaveAttribute("disabled", "");
  });

  test("mutationAllowed surfaces: primary on, advanced off, object_write scaffold off", async ({
    page,
  }) => {
    await expect(page.getByTestId("gate-mutation-allowed")).toHaveText("yes");
    await expect(page.getByTestId("gate-advanced-mutation-allowed")).toHaveText("no");
    await expect(page.getByTestId("gate-scaffold-apply-allowed")).toHaveText("yes");
    await expect(page.getByTestId("gate-scaffold-object-write")).toHaveText("no");
    await expect(page.getByTestId("gate-below-min-major-19")).toHaveText("yes");
    await expect(page.getByTestId("gate-currency-field")).toHaveText("no");
    await expect(page.getByTestId("gate-default-view-mode")).toHaveText("tree,form");

    await expect(page.getByTestId("mutate-primary")).toBeEnabled();
    await expect(page.getByTestId("mutate-advanced")).toBeDisabled();
  });
});

test.describe("Mutation gates (mock Odoo 19 GA)", () => {
  test("enables update_path actions and advanced mutate", async ({ page }) => {
    await page.goto("/e2e/automation-caps");
    await page.getByTestId("harness-profile").selectOption("odoo19");
    await expect(page.getByTestId("harness-major")).toHaveText(/19/);

    const select = page.getByTestId("automation-action-kind");
    await expect(select.locator('option[value="update_field"]')).not.toHaveAttribute(
      "disabled",
      "",
    );
    await expect(select.locator('option[value="related_write"]')).not.toHaveAttribute(
      "disabled",
      "",
    );

    await expect(page.getByTestId("gate-mutation-allowed")).toHaveText("yes");
    await expect(page.getByTestId("gate-advanced-mutation-allowed")).toHaveText("yes");
    await expect(page.getByTestId("gate-scaffold-object-write")).toHaveText("yes");
    await expect(page.getByTestId("gate-below-min-major-19")).toHaveText("no");
    await expect(page.getByTestId("gate-currency-field")).toHaveText("yes");
    await expect(page.getByTestId("gate-default-view-mode")).toHaveText("list,form");
    await expect(page.getByTestId("mutate-advanced")).toBeEnabled();
  });
});

test.describe("Mutation gates (unprobed connection)", () => {
  test("fail-closed: greys out primary + advanced mutate", async ({ page }) => {
    await page.goto("/e2e/automation-caps");
    await page.getByTestId("harness-profile").selectOption("unprobed");
    await expect(page.getByTestId("harness-major")).toHaveText(/unknown/);

    await expect(page.getByTestId("gate-mutation-allowed")).toHaveText("no");
    await expect(page.getByTestId("gate-advanced-mutation-allowed")).toHaveText("no");
    await expect(page.getByTestId("gate-scaffold-apply-allowed")).toHaveText("no");
    await expect(page.getByTestId("gate-below-min-major-19")).toHaveText("yes");
    await expect(page.getByTestId("gate-default-view-mode")).toHaveText("tree,form");
    await expect(page.getByTestId("mutate-primary")).toBeDisabled();
    await expect(page.getByTestId("mutate-advanced")).toBeDisabled();
  });
});
