import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

let search = new URLSearchParams();
const push = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => "/connections/c1/suite/setup",
  useRouter: () => ({ push }),
  useSearchParams: () => search,
  useParams: () => ({ id: "c1" }),
}));

const home = {
  passport: { version: "19.0-20251001", major: 19, edition: "community", hosting: "onprem", database: "acme", url: "http://x", apps: ["Sales", "CRM"],
    companies: [{ id: 1, name: "Acme", country: "Nigeria", currency: "NGN" }], languages: ["en_US"], localization: ["l10n_ng"] },
  writes: { on: false, mode: "observer", paused: false }, facts: { posted_entries: 0, done_moves: 0 }, needs_you: [], recent_runs: [],
};
const step = (id: string, type: string, label: string) => ({ id, type, task: "2.6#65", label, inputs: {}, depends_on: [], company_id: null,
  source: { kind: "workbook", ref: "Units row 3" }, reversibility: type === "install" ? "one_way" : "remove", risk: "high", rank: type === "install" ? 0 : 5 });
const plan = (check: unknown) => ({ id: "p1", name: "Units", created_at: null, payload: {
  kind: "setup", steps: [step("i", "install", "Install board"), step("u", "units", "Add unit Box")], waves: [["i"], ["u"]], order_errors: [], hash: "h1",
  rank_labels: { i: "Install apps", u: "Units, categories and products" }, check, approval: null } });
const report = { facts: { posted_entries: 0, done_moves: 0 }, waves: [["i"], ["u"]], errors: [], steps: {
  i: { id: "i", verdict: "ready", message: "Will install board.", changes: {} }, u: { id: "u", verdict: "ready", message: "Will add Box = 6 x Units.", changes: {} } },
  counts: { ready: 2, no_change: 0, needs_input: 0, blocked: 0, waiting: 0 }, can_apply: true, needs_approval: false, threshold: 200,
  plan_hash: "h1", checked_at: "2026-10-16T03:00:00Z", receipt: "r1" };

const api = vi.hoisted(() => ({
  home: vi.fn(), runs: vi.fn(), plan: vi.fn(), check: vi.fn(), run: vi.fn(), getRun: vi.fn(), carryOn: vi.fn(), stop: vi.fn(), undoPlan: vi.fn(),
  catalog: vi.fn(), plans: vi.fn(),
}));
vi.mock("@/lib/api/suite", () => ({ suiteApi: api, changeApi: new Proxy({}, { get: () => vi.fn().mockResolvedValue({ runs: [], batches: [] }) }) }));

import { SuiteShell } from "./SuiteShell";
import { SetupWorkspace } from "./SetupWorkspace";
import { SuiteHome } from "./SuiteHome";

beforeEach(() => {
  vi.clearAllMocks();
  search = new URLSearchParams();
  api.home.mockResolvedValue(home);
  api.runs.mockResolvedValue({ runs: [] });
  api.plans.mockResolvedValue({ plans: [] });
});

describe("suite shell", () => {
  it("shows the version exactly as the database reports it, with no switcher, and Writes Off", async () => {
    render(<SuiteShell connectionId="c1"><SuiteHome /></SuiteShell>);
    expect(await screen.findAllByText(/19\.0-20251001/)).not.toHaveLength(0);
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(screen.queryByRole("listbox")).toBeNull();
    expect(screen.getByTestId("suite-writes").textContent).toContain("Writes: Off");
    expect(screen.getByRole("navigation", { name: "Suite" })).toBeTruthy();
    expect(screen.getByText("Nothing needs you right now.")).toBeTruthy();
    fireEvent.click(screen.getByTestId("suite-passport-chip"));
    expect(screen.getAllByTestId("suite-passport").length).toBeGreaterThan(0);
  });
});

describe("set up board", () => {
  it("keeps Run disabled until a check receipt exists for this exact plan", async () => {
    search = new URLSearchParams("plan=p1&view=board");
    api.plan.mockResolvedValueOnce(plan(null)).mockResolvedValue(plan(report));
    api.check.mockResolvedValue(report);
    api.run.mockResolvedValue({ id: "r1" });
    render(<SuiteShell connectionId="c1"><SetupWorkspace /></SuiteShell>);
    const run = await screen.findByTestId("suite-run");
    expect((run as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByLabelText("Wave 1").textContent).toContain("installs");
    expect(screen.getAllByText("Hard to undo").length).toBe(1);
    fireEvent.click(screen.getByTestId("suite-check"));
    await waitFor(() => expect((screen.getByTestId("suite-run") as HTMLButtonElement).disabled).toBe(false));
    expect(screen.getByTestId("suite-check-report").textContent).toContain("2 ready");
    fireEvent.click(screen.getByTestId("suite-run"));
    await waitFor(() => expect(push).toHaveBeenCalled());
    expect(String(push.mock.calls[0][0])).toContain("run=r1");
  });

  it("a paused run offers skip and carry on, then the undo plan", async () => {
    search = new URLSearchParams("run=r1&view=run");
    api.getRun.mockResolvedValue({ id: "r1", name: "Units", payload: { plan_id: "p1", kind: "setup", state: "paused", started_at: "", finished_at: null,
      waves: [{ n: 1, steps: [{ id: "u", label: "Add unit Box", state: "failed", message: "Paused: the unit 'Units' is gone." }] }] } });
    render(<SuiteShell connectionId="c1"><SetupWorkspace /></SuiteShell>);
    expect(await screen.findByTestId("suite-carry-on")).toBeTruthy();
    expect(screen.getByText(/Failed: Paused: the unit/)).toBeTruthy();
    expect(screen.getByTestId("suite-undo")).toBeTruthy();
    expect(screen.getByTestId("suite-stop")).toBeTruthy();
  });
});
