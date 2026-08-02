import { expect, test } from "@playwright/test";

const PHRASE = "I understand the risks";

test.describe("ConfirmDialog", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/e2e/confirm");
    await page.getByTestId("open-confirm").click();
    await expect(page.getByTestId("confirm-dialog")).toBeVisible();
  });

  test("Confirm button disabled until exact phrase typed", async ({ page }) => {
    const confirm = page.getByTestId("confirm-dialog-confirm");
    await expect(confirm).toBeDisabled();

    await page.getByTestId("confirm-dialog-input").fill(PHRASE);
    await expect(confirm).toBeEnabled();
  });

  test("Wrong phrase keeps Confirm disabled", async ({ page }) => {
    const confirm = page.getByTestId("confirm-dialog-confirm");
    await page.getByTestId("confirm-dialog-input").fill("I understand the risk");
    await expect(confirm).toBeDisabled();
  });

  test("Correct phrase + Confirm shows confirmed:ok", async ({ page }) => {
    await page.getByTestId("confirm-dialog-input").fill(PHRASE);
    await page.getByTestId("confirm-dialog-confirm").click();
    await expect(page.getByTestId("confirm-result")).toHaveText("confirmed:ok");
    await expect(page.getByTestId("confirm-dialog")).toHaveCount(0);
  });

  test("Cancel shows confirmed:cancelled", async ({ page }) => {
    await page.getByTestId("confirm-dialog-cancel").click();
    await expect(page.getByTestId("confirm-result")).toHaveText(
      "confirmed:cancelled",
    );
    await expect(page.getByTestId("confirm-dialog")).toHaveCount(0);
  });
});
