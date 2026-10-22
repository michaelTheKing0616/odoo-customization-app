import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("./SuiteContext", () => ({ useSuite: () => ({ connectionId: "c1" }), errText: (e: unknown) => String(e) }));
const api = vi.hoisted(() => ({ checkEveryVersion: vi.fn(), forecast: vi.fn(), list: vi.fn() }));
vi.mock("@/lib/api/suite", () => ({ suiteApi: { checkEveryVersion: api.checkEveryVersion }, upkeepApi: { forecast: api.forecast } }));
vi.mock("@/lib/api/connections", () => ({ connectionsApi: { listConnections: api.list } }));

import { CheckEveryVersion, UpgradeForecastPanel } from "./EveryVersion";

describe("suite stage 4", () => {
  afterEach(cleanup);

  it("checks a plan on other databases and says where it differs", async () => {
    api.list.mockResolvedValue([{ id: "c1", name: "Here" }, { id: "c20", name: "Test copy 20" }]);
    api.checkEveryVersion.mockResolvedValue({ same_everywhere: false, results: [
      { connection_id: "c1", version: "19", can_apply: true, counts: { ready: 3, blocked: 0, needs_input: 0 }, problems: [] },
      { connection_id: "c20", version: "20", can_apply: false, counts: { ready: 2, blocked: 1, needs_input: 0 }, problems: [{ step: "s2", verdict: "blocked", message: "uom.category is not on this database." }] }] });
    render(<CheckEveryVersion planId="p1" />);
    fireEvent.click(await screen.findByLabelText(/Test copy 20/));
    fireEvent.click(screen.getByTestId("every-version-run"));
    expect(await screen.findByText(/differs between databases/)).toBeTruthy();
    expect(screen.getByText(/uom.category is not on this database/)).toBeTruthy();
    expect(api.checkEveryVersion).toHaveBeenCalledWith("c1", "p1", ["c20"]);
  });

  it("shows what each newer version needs before an upgrade", async () => {
    api.forecast.mockResolvedValue({ from_version: 18, summary: "1 screen change(s) and 1 data move(s) to plan for. Rehearse on a copy first.",
      steps: [{ version: 19, screens_to_fix: 1, auto_fixable: 1, screens: [], data_moves: ["Employee contracts move into employee versions."] }, { version: 20, screens_to_fix: 0, auto_fixable: 0, screens: [], data_moves: [] }] });
    render(<UpgradeForecastPanel />);
    expect(await screen.findByText(/Rehearse on a copy first/)).toBeTruthy();
    expect(screen.getByRole("rowheader", { name: "19" })).toBeTruthy();
    expect(screen.getByText(/employee versions/)).toBeTruthy();
  });
});
