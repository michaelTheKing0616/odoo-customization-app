import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LiveDatabaseSection } from "./LiveDatabaseSection";

const getLiveSnapshot = vi.fn();
const getSnapshotModel = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    getLiveSnapshot: (...a: unknown[]) => getLiveSnapshot(...a),
    getSnapshotModel: (...a: unknown[]) => getSnapshotModel(...a),
  },
}));

const SNAP = {
  ok: true, major: 20, series: "20.0", server_version: "20.0", edition: "community", hosting: "onprem",
  support: "supported", apps: [{ name: "sale", label: "Sales" }], modules: ["base", "sale"],
  counts: { modules: 4, modules_hidden: 2, apps: 1, models: 2, custom_models: 1, automations: 1, scheduled_actions: 1, groups: 1 },
  custom_models: [{ model: "x_renewal", label: "Renewal" }],
  models: [{ model: "res.partner", label: "Contact" }, { model: "x_renewal", label: "Renewal" }],
  automations: [{ name: "Renewal reminder", model_id: "Renewal", trigger: "on_time" }],
  scheduled_actions: [{ cron_name: "Nightly", interval_number: "1", interval_type: "days" }],
  groups: [{ name: "Manager", category: "Sales" }],
  can_change: [
    { key: "custom_fields", available: "yes", reason: "" },
    { key: "python_module_install", available: "no", reason: "Online" },
  ],
  problems: [],
  attention: [] as unknown[],
};

const ATTN = [
  { key: "custom_model_setup", severity: "warning", rank: 2, title: "1 custom model can't be opened by your team",
    detail: "Renewal has no access rules.", count: 1, drill: { section: "explorer", model: "x_renewal", tab: "rules" }, names: ["x_renewal"] },
  { key: "failing_crons", severity: "critical", rank: 1, title: "1 scheduled action is failing",
    detail: "Nightly failed 3 times.", count: 1, drill: { section: "automations" }, names: ["Nightly"] },
];

const DETAIL = {
  model: "x_renewal", label: "Renewal", custom: true,
  fields: [{ name: "x_owner_id", type: "many2one", string: "Owner", required: false, relation: "res.users", selection: [] }],
  views: { types: ["form", "list"], form_field_count: 2, form_fields: ["x_name", "x_owner_id"] },
  server_actions: [], menus: ["Renewals / All"],
  record_rules: { source: "ir.access", rows: [{ name: "own", group: "User", operation: "crud", domain: "[('x_owner_id','=',user.id)]", kind: "permission" }] },
  problems: [],
};

afterEach(() => { cleanup(); vi.clearAllMocks(); window.history.replaceState(null, "", "/"); });

describe("LiveDatabaseSection", () => {
  it("shows the live picture: header, capabilities, apps, custom models, automations", async () => {
    getLiveSnapshot.mockResolvedValue(SNAP);
    render(<LiveDatabaseSection connectionId="c1" />);
    expect(screen.getByTestId("live-loading")).toBeInTheDocument();
    await screen.findByTestId("live-snapshot");
    expect(screen.getByTestId("live-header")).toHaveTextContent("Odoo 20.0");
    expect(screen.getByTestId("live-header")).toHaveTextContent("Self-hosted");
    expect(screen.getByTestId("live-header")).toHaveTextContent("2 localisation/theme/test modules hidden");
    const can = screen.getByTestId("live-can-change");
    expect(can).toHaveTextContent("Add fields to any record");
    expect(can).toHaveTextContent("Custom code modules · Not on this plan");
    expect(screen.getByTestId("live-apps")).toHaveTextContent("Sales");
    expect(screen.getByTestId("live-custom-models")).toHaveTextContent("x_renewal");
    expect(screen.getByTestId("live-automations")).toHaveTextContent("Renewal reminder");
    expect(screen.getByTestId("live-automations")).toHaveTextContent("every 1 days");
    // Editing is opt-in: the only entry before any click is "Add an app"; nothing installs or edits directly.
    expect(screen.queryByRole("button", { name: /^(edit|install)/i })).toBeNull();
    expect(screen.getByTestId("add-app")).toBeInTheDocument();
    expect(screen.getByTestId("attention-clear")).toHaveTextContent("Nothing needs your attention");
    expect(screen.getByTestId("summary-custom-models")).toHaveTextContent("1");
  });

  it("explains an unreachable database and retries", async () => {
    getLiveSnapshot.mockRejectedValueOnce(new Error("Couldn't reach your database.")).mockResolvedValue(SNAP);
    render(<LiveDatabaseSection connectionId="c1" />);
    expect(await screen.findByText("Couldn't reach your database")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByTestId("live-snapshot");
  });

  it("explorer searches the index and lazy-loads one model", async () => {
    getLiveSnapshot.mockResolvedValue(SNAP);
    getSnapshotModel.mockResolvedValue(DETAIL);
    render(<LiveDatabaseSection connectionId="c1" />);
    await screen.findByTestId("model-explorer");
    expect(getSnapshotModel).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Search models"), { target: { value: "renew" } });
    expect(screen.queryByText("res.partner")).toBeNull();
    fireEvent.click(screen.getByRole("option", { name: /Renewal/ }));
    const detail = await screen.findByTestId("explorer-detail");
    expect(getSnapshotModel).toHaveBeenCalledWith("c1", "x_renewal");
    expect(detail).toHaveTextContent("→ res.users");
    fireEvent.click(screen.getByRole("tab", { name: /Views/ }));
    expect(await screen.findByTestId("tab-views")).toHaveTextContent("form shows 2 fields");
    fireEvent.click(screen.getByRole("tab", { name: /Menus/ }));
    expect(await screen.findByTestId("tab-menus")).toHaveTextContent("Renewals / All");
    fireEvent.click(screen.getByRole("tab", { name: /rules/i }));
    expect(await screen.findByTestId("explorer-rules")).toHaveTextContent("user.id");
  });

  it("explorer shows an honest error for one model", async () => {
    getLiveSnapshot.mockResolvedValue(SNAP);
    getSnapshotModel.mockRejectedValue(new Error("Couldn't reach your database."));
    render(<LiveDatabaseSection connectionId="c1" />);
    await screen.findByTestId("model-explorer");
    fireEvent.click(screen.getByRole("option", { name: /Contact/ }));
    await waitFor(() => expect(screen.getByTestId("explorer-error")).toHaveTextContent("Couldn't load res.partner"));
  });

  it("ranks attention by severity and drills into the explorer on the right tab", async () => {
    getLiveSnapshot.mockResolvedValue({ ...SNAP, attention: ATTN });
    getSnapshotModel.mockResolvedValue({ ...DETAIL, record_rules: { source: "ir.access", rows: [] } });
    render(<LiveDatabaseSection connectionId="c1" />);
    const strip = await screen.findByTestId("attention");
    expect(screen.queryByTestId("attention-clear")).toBeNull();
    const text = strip.textContent ?? "";
    expect(text.indexOf("scheduled action is failing")).toBeLessThan(text.indexOf("can't be opened"));
    expect(getSnapshotModel).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /Open model/ }));
    await waitFor(() => expect(getSnapshotModel).toHaveBeenCalledWith("c1", "x_renewal"));
    expect(await screen.findByTestId("tab-rules")).toHaveTextContent("only the administrator");
  });

  it("summary cards and custom models drill to their sections", async () => {
    getLiveSnapshot.mockResolvedValue(SNAP);
    getSnapshotModel.mockResolvedValue(DETAIL);
    const scroll = vi.fn();
    Element.prototype.scrollIntoView = scroll;
    render(<LiveDatabaseSection connectionId="c1" />);
    fireEvent.click(await screen.findByTestId("summary-automations"));
    expect(scroll).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /Renewal\s*x_renewal/ }));
    await waitFor(() => expect(getSnapshotModel).toHaveBeenCalledWith("c1", "x_renewal"));
    expect(await screen.findByTestId("tab-fields")).toHaveTextContent("Owner");
  });

  it("keeps the selected model and tab in the URL; Back returns to the previous model", async () => {
    getLiveSnapshot.mockResolvedValue(SNAP);
    getSnapshotModel.mockImplementation((_c: string, m: string) => Promise.resolve({ ...DETAIL, model: m, label: m }));
    render(<LiveDatabaseSection connectionId="c1" />);
    await screen.findByTestId("model-explorer");
    fireEvent.click(screen.getByRole("option", { name: /Contact/ }));
    await waitFor(() => expect(window.location.search).toBe("?model=res.partner"));
    fireEvent.click(screen.getByRole("option", { name: /Renewal/ }));
    await waitFor(() => expect(window.location.search).toBe("?model=x_renewal"));
    fireEvent.click(await screen.findByRole("tab", { name: /Menus/ }));
    expect(window.location.search).toBe("?model=x_renewal&tab=menus");
    window.history.back();
    await waitFor(() => expect(window.location.search).toBe("?model=res.partner"));
    window.dispatchEvent(new PopStateEvent("popstate")); // browsers fire this on Back; jsdom may not
    await waitFor(() => expect(screen.getByTestId("explorer-detail")).toHaveTextContent("res.partner"));
  });

  it("restores model + tab from the URL on load (shareable link)", async () => {
    window.history.replaceState(null, "", "/?model=x_renewal&tab=views");
    getLiveSnapshot.mockResolvedValue(SNAP);
    getSnapshotModel.mockResolvedValue(DETAIL);
    render(<LiveDatabaseSection connectionId="c1" />);
    expect(await screen.findByTestId("tab-views")).toHaveTextContent("form shows 2 fields");
    expect(getSnapshotModel).toHaveBeenCalledWith("c1", "x_renewal");
  });

  it("skips the arrival tint when reduced motion is preferred", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const original = window.matchMedia;
    const mm = vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() });
    Object.defineProperty(window, "matchMedia", { configurable: true, value: mm });
    Element.prototype.scrollIntoView = vi.fn();
    getLiveSnapshot.mockResolvedValue(SNAP);
    render(<LiveDatabaseSection connectionId="c1" />);
    fireEvent.click(await screen.findByTestId("summary-automations"));
    const target = screen.getByTestId("live-automations");
    expect(target).not.toHaveAttribute("data-flash");
    expect(target.className).not.toContain("overview-arrive");
    expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith(expect.objectContaining({ behavior: "auto" }));
    vi.useRealTimers();
    Object.defineProperty(window, "matchMedia", { configurable: true, value: original });
  });

  it("keyboard: '/' focuses search, arrows move through models, Enter opens", async () => {
    getLiveSnapshot.mockResolvedValue(SNAP);
    getSnapshotModel.mockResolvedValue(DETAIL);
    render(<LiveDatabaseSection connectionId="c1" />);
    const search = await screen.findByLabelText("Search models");
    fireEvent.keyDown(document.body, { key: "/" });
    expect(document.activeElement).toBe(search);
    fireEvent.keyDown(search, { key: "ArrowDown" });
    const opts = screen.getAllByRole("option");
    expect(document.activeElement).toBe(opts[0]); // custom first: x_renewal
    fireEvent.keyDown(opts[0], { key: "ArrowDown" });
    expect(document.activeElement).toBe(opts[1]);
    fireEvent.keyDown(opts[1], { key: "ArrowUp" });
    expect(document.activeElement).toBe(opts[0]);
    fireEvent.click(opts[0]); // Enter on a focused button fires click
    await waitFor(() => expect(getSnapshotModel).toHaveBeenCalledWith("c1", "x_renewal"));
  });

  it("passes the snapshot up so the page can derive counts", async () => {
    getLiveSnapshot.mockResolvedValue(SNAP);
    const onSnapshot = vi.fn();
    render(<LiveDatabaseSection connectionId="c1" onSnapshot={onSnapshot} capabilityExtras={<p>extras-slot</p>} />);
    await waitFor(() => expect(onSnapshot).toHaveBeenCalledWith(expect.objectContaining({ counts: SNAP.counts })));
    expect(screen.getByTestId("live-can-change")).toHaveTextContent("extras-slot");
  });

  it("tints the drill target briefly, then clears it", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    Element.prototype.scrollIntoView = vi.fn();
    getLiveSnapshot.mockResolvedValue(SNAP);
    render(<LiveDatabaseSection connectionId="c1" />);
    fireEvent.click(await screen.findByTestId("summary-apps"));
    const target = screen.getByTestId("live-apps");
    expect(target).toHaveClass("overview-arrive");
    expect(target.className).not.toMatch(/ring-/);
    vi.advanceTimersByTime(1300);
    expect(target).not.toHaveClass("overview-arrive");
    vi.useRealTimers();
  });
});
