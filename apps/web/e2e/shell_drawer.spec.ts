/** Locked oracle for UI-SHELL-DRAWER. Worker must not edit this file. */
import { expect, test, type Browser, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const HARNESS_PATH = "/e2e/shell-drawer";
const THEME_KEY = "odoo-custom-theme";

type ThemeName = "light" | "dark";

type ShellMetrics = {
  docScrollWidth: number;
  docClientWidth: number;
  shellScrollWidth: number;
  shellClientWidth: number;
  sidebarShown: boolean;
  sidebarOutOfFlow: boolean;
  sidebarVisibleWidth: number;
  sidebarVisibleHeight: number;
  navAvailable: boolean;
};

async function withTheme(
  browser: Browser,
  baseURL: string | undefined,
  theme: ThemeName,
  viewport: { width: number; height: number },
  run: (page: Page) => Promise<void>,
) {
  const context = await browser.newContext({
    baseURL: baseURL ?? "http://127.0.0.1:3114",
    viewport,
  });
  const page = await context.newPage();
  await page.addInitScript((value: ThemeName) => {
    localStorage.setItem("odoo-custom-theme", value);
    document.documentElement.classList.toggle("dark", value === "dark");
  }, theme);
  try {
    await run(page);
  } finally {
    await context.close();
  }
}

async function openHarness(page: Page) {
  const response = await page.goto(HARNESS_PATH);
  if (!response) throw new Error(`GET ${HARNESS_PATH} returned no response`);
  expect(response.status(), `GET ${HARNESS_PATH}`).toBe(200);
  await expect(page.getByTestId("app-shell")).toBeVisible();
}

async function readShell(page: Page): Promise<ShellMetrics> {
  return page.evaluate(() => {
    const shownMin = 8;

    function visibleSpan(el: Element): { width: number; height: number } {
      const rect = el.getBoundingClientRect();
      const width = Math.min(rect.right, window.innerWidth) - Math.max(rect.left, 0);
      const height = Math.min(rect.bottom, window.innerHeight) - Math.max(rect.top, 0);
      return { width: Math.max(0, width), height: Math.max(0, height) };
    }

    function isPainted(el: Element): boolean {
      let current: Element | null = el;
      while (current) {
        const style = getComputedStyle(current);
        if (
          style.display === "none" ||
          style.visibility === "hidden" ||
          style.visibility === "collapse"
        ) {
          return false;
        }
        const opacity = Number.parseFloat(style.opacity);
        if (Number.isFinite(opacity) && opacity < 0.99) return false;
        current = current.parentElement;
      }
      const box = visibleSpan(el);
      return box.width > shownMin && box.height > shownMin;
    }

    function isOutOfFlow(el: Element): boolean {
      let current: Element | null = el;
      while (current && current !== document.documentElement) {
        const style = getComputedStyle(current);
        if (style.display === "none") return true;
        if (style.position === "fixed" || style.position === "absolute") return true;
        current = current.parentElement;
      }
      return false;
    }

    const shell = document.querySelector('[data-testid="app-shell"]');
    const sidebar = document.querySelector('[data-testid="app-sidebar"]');
    const shellEl = shell instanceof HTMLElement ? shell : null;
    const doc = document.documentElement;
    const span = sidebar ? visibleSpan(sidebar) : { width: 0, height: 0 };
    let navAvailable = false;
    if (sidebar) {
      const nav = sidebar.querySelector("nav");
      if (nav && isPainted(nav)) {
        for (const link of nav.querySelectorAll("a")) {
          if (isPainted(link)) {
            navAvailable = true;
            break;
          }
        }
      }
    }

    return {
      docScrollWidth: doc.scrollWidth,
      docClientWidth: doc.clientWidth,
      shellScrollWidth: shellEl ? shellEl.scrollWidth : Number.POSITIVE_INFINITY,
      shellClientWidth: shellEl ? shellEl.clientWidth : 0,
      sidebarShown: sidebar ? isPainted(sidebar) : false,
      sidebarOutOfFlow: sidebar ? isOutOfFlow(sidebar) : true,
      sidebarVisibleWidth: span.width,
      sidebarVisibleHeight: span.height,
      navAvailable,
    };
  });
}

function offCanvasProblem(metrics: ShellMetrics): string {
  const problems: string[] = [];
  if (metrics.sidebarShown) problems.push("sidebar is shown");
  if (!metrics.sidebarOutOfFlow) problems.push("sidebar is in the document flow");
  if (!(metrics.docClientWidth > 0)) problems.push("documentElement has no client width");
  if (metrics.docScrollWidth > metrics.docClientWidth) {
    problems.push(
      `documentElement scrollWidth ${metrics.docScrollWidth} > clientWidth ${metrics.docClientWidth}`,
    );
  }
  if (!(metrics.shellClientWidth > 0)) problems.push("app-shell has no client width");
  if (metrics.shellScrollWidth > metrics.shellClientWidth) {
    problems.push(
      `app-shell scrollWidth ${metrics.shellScrollWidth} > clientWidth ${metrics.shellClientWidth}`,
    );
  }
  return problems.join("; ");
}

function navProblem(metrics: ShellMetrics): string {
  return metrics.navAvailable ? "" : "sidebar navigation is not available";
}

function dockProblem(metrics: ShellMetrics): string {
  const problems: string[] = [];
  if (!metrics.sidebarShown) problems.push("docked sidebar is not shown");
  if (metrics.sidebarOutOfFlow) problems.push("sidebar is not the in-flow docked column");
  if (metrics.sidebarVisibleWidth < 48) {
    problems.push(`visible width ${metrics.sidebarVisibleWidth} < 48`);
  }
  if (metrics.sidebarVisibleHeight < 200) {
    problems.push(`visible height ${metrics.sidebarVisibleHeight} < 200`);
  }
  return problems.join("; ");
}

async function expectShellAxeClean(page: Page, theme: ThemeName, label: string) {
  await page.evaluate((isDark: boolean) => {
    document.documentElement.classList.toggle("dark", isDark);
  }, theme === "dark");
  const results = await new AxeBuilder({ page }).include('[data-testid="app-shell"]').analyze();
  const serious = results.violations
    .filter((violation) => violation.impact === "serious" || violation.impact === "critical")
    .map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      help: violation.help,
      targets: violation.nodes.slice(0, 5).map((node) => node.target),
    }));
  expect(serious, `${label} (${theme})`).toEqual([]);
}

test.describe("UI-SHELL-DRAWER", () => {
  test("below sm, the closed sidebar is an off-canvas drawer without horizontal scroll in light and dark", async ({
    browser,
    baseURL,
  }) => {
    test.setTimeout(120_000);
    for (const theme of ["light", "dark"] as const) {
      await test.step(theme, async () => {
        await withTheme(browser, baseURL, theme, { width: 390, height: 844 }, async (page) => {
          await openHarness(page);
          await expect
            .poll(async () => offCanvasProblem(await readShell(page)), { timeout: 10_000 })
            .toBe("");
          await expectShellAxeClean(page, theme, "drawer closed");

          const openSidebar = page.getByRole("button", { name: "Open sidebar", exact: true });
          await expect(openSidebar, 'control named "Open sidebar"').toBeVisible();
          await openSidebar.click();
          await expect
            .poll(async () => navProblem(await readShell(page)), { timeout: 10_000 })
            .toBe("");
          await expectShellAxeClean(page, theme, "drawer open");

          await page.keyboard.press("Escape");
          await expect
            .poll(async () => offCanvasProblem(await readShell(page)), { timeout: 10_000 })
            .toBe("");
        });
      });
    }
  });

  test.describe("desktop", () => {
    test.use({ viewport: { width: 1440, height: 900 } });

    test("from sm up, the docked sidebar stays visible", async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 900 });
      await openHarness(page);
      await expect
        .poll(async () => dockProblem(await readShell(page)), { timeout: 10_000 })
        .toBe("");
    });
  });
});
