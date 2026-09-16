/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const listConfigRecipes = vi.fn();
const runDay1Setup = vi.fn();
const numberingCatalog = vi.fn();
const listCompanies = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    listConfigRecipes: (...a: unknown[]) => listConfigRecipes(...a),
    runDay1Setup: (...a: unknown[]) => runDay1Setup(...a),
    numberingCatalog: (...a: unknown[]) => numberingCatalog(...a),
    runNumberingPack: vi.fn(),
    listAppsPacks: vi.fn().mockResolvedValue([]),
    runAppsPack: vi.fn(),
    getSettingsBoard: vi.fn().mockResolvedValue({ allowlist: [], values: {} }),
    patchSettingsBoard: vi.fn(),
    runMultiCompany: vi.fn(),
    listMasterPacks: vi.fn().mockResolvedValue([]),
    runMasterPack: vi.fn(),
    listCompanies: (...a: unknown[]) => listCompanies(...a),
  },
  ConfirmationRequiredError: class ConfirmationRequiredError extends Error {},
}));

import { ConfigCommandCenter } from "./ConfigCommandCenter";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

beforeEach(() => {
  listConfigRecipes.mockResolvedValue([
    {
      id: "day1",
      phase: "p0",
      title: "Day-1 setup",
      blurb: "Company name, currency, country, language.",
      clicks: "3 clicks",
    },
    {
      id: "numbering",
      phase: "p0",
      title: "Document numbering",
      blurb: "SO / INV / PO prefixes.",
      clicks: "2 clicks",
    },
    {
      id: "import-seeds",
      phase: "p1",
      title: "Import starter packs",
      blurb: "Open Import gallery.",
      clicks: "Open Import",
    },
    {
      id: "bulk-recipes",
      phase: "p1",
      title: "Bulk recipes",
      blurb: "Open Bulk Suite.",
      clicks: "Open Bulk",
    },
  ]);
  listCompanies.mockResolvedValue([{ id: 1, name: "My Company" }]);
  numberingCatalog.mockResolvedValue([
    { key: "sale", name: "Sales Orders", code: "sale.order", prefix: "SO/", padding: 5 },
  ]);
  runDay1Setup.mockResolvedValue({
    ok: true,
    dry_run: true,
    steps: [{ op: "write_company", target: "res.company.name", detail: "Rename" }],
    applied: [],
    warnings: [],
    message: "Dry-run Day-1",
  });
});

describe("ConfigCommandCenter", () => {
  it("renders recipe cards from catalog", async () => {
    render(<ConfigCommandCenter connectionId="conn-1" />);
    await waitFor(() => {
      expect(screen.getByTestId("config-command-center")).toBeTruthy();
    });
    expect(screen.getByTestId("recipe-card-day1").textContent).toMatch(/Day-1/);
    expect(screen.getByTestId("recipe-card-numbering")).toBeTruthy();
    expect(screen.getByTestId("recipe-card-import-seeds")).toBeTruthy();
    expect(screen.getByTestId("recipe-card-bulk-recipes")).toBeTruthy();
    expect(listConfigRecipes).toHaveBeenCalledWith("conn-1");
  });

  it("opens Day-1 panel and dry-runs", async () => {
    render(<ConfigCommandCenter connectionId="conn-1" />);
    await waitFor(() => screen.getByTestId("recipe-card-day1"));
    fireEvent.click(screen.getByTestId("recipe-card-day1").querySelector("button")!);
    await waitFor(() => screen.getByTestId("day1-panel"));
    await waitFor(() => expect(screen.getByDisplayValue("My Company")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /^Dry-run$/i }));
    await waitFor(() => {
      expect(runDay1Setup).toHaveBeenCalled();
      expect(screen.getByTestId("recipe-plan-preview").textContent).toMatch(/Dry-run/i);
    });
  });
});
