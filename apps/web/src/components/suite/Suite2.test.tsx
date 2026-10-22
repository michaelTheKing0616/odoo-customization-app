import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => "/connections/c1/suite/change/edit",
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({ id: "c1" }),
}));
vi.mock("./SuiteContext", () => ({ useSuite: () => ({ connectionId: "c1", home: null, readAt: null }), errText: (e: unknown) => String(e) }));

const api = vi.hoisted(() => ({
  change: { buttons: vi.fn(), users: vi.fn(), fields: vi.fn(), create: vi.fn(), update: vi.fn(), get: vi.fn(), check: vi.fn(), run: vi.fn(), getRun: vi.fn(), scan: vi.fn(), requestApproval: vi.fn(), stop: vi.fn(), undo: vi.fn(), exportCsv: vi.fn() },
  upkeep: { schedules: vi.fn(), pause: vi.fn(), resume: vi.fn(), ask: vi.fn(), askStream: vi.fn(), ticket: vi.fn(), guideTopics: vi.fn(), guide: vi.fn(), files: vi.fn() },
}));
const rec = vi.hoisted(() => ({ models: vi.fn(), meta: vi.fn(), search: vi.fn(), replacePreview: vi.fn(), plan: vi.fn() }));
vi.mock("@/lib/api/suite", () => ({ changeApi: api.change, upkeepApi: api.upkeep, suiteApi: {}, recordsApi: rec }));

import { Ask } from "./Ask";
import { ChangeRecords, parseIds } from "./ChangeRecords";
import { RecordEditor, parsePaste, showValue } from "./RecordEditor";
import { buildStep } from "./SetupBuilders";
import { Upkeep, bytes } from "./Upkeep";

const cron = (id: number, description: string, extra = {}) => ({ id, name: `Job ${id}`, record_type: "Contact", how_often: "every day", description, description_source: "catalogue",
  active: true, next_run: "2026-10-16 10:00:00", last_result: "Last ran 2026-10-15 10:00:00", failing: false, paused: null, next_24h: [], ...extra });

describe("suite stage 2", () => {
  afterEach(cleanup);
  beforeEach(() => { Object.values(api.change).concat(Object.values(api.upkeep)).forEach((f) => f.mockReset()); push.mockReset(); });

  it("scheduled action cards never show method names", async () => {
    api.upkeep.schedules.mockResolvedValue({ now: "", schedules: [cron(1, "Sends the emails waiting in the outgoing queue."), cron(2, "Runs every 2 days on Contact.", { description_source: "plain fallback" }),
      cron(3, "Updates currency exchange rates.", { active: false, paused: { by: "ada@x.test", at: "2026-10-16T09:00:00Z", reason: "Bank feed down" } })] });
    render(<Upkeep area="schedules" />);
    const cells = await screen.findAllByTestId("cron-description");
    expect(cells).toHaveLength(3);
    for (const c of cells) expect(c.textContent ?? "").not.toMatch(/\.\w*\(|\w+_\w+\(/);
    expect(screen.getByText(/Bank feed down/)).toBeTruthy();
    fireEvent.click(screen.getAllByRole("button", { name: "Pause" })[0]);
    const form = screen.getByLabelText("Why pause it").closest("form") as HTMLElement;
    expect(within(form).getByRole("button", { name: "Pause" }).hasAttribute("disabled")).toBe(true);
  });

  it("edit batch: check shows the money guard refusal and no run", async () => {
    api.change.fields.mockResolvedValue({ fields: [{ name: "payment_term_id", label: "Payment Terms", type: "many2one", relation: "account.payment.term", choices: [] }] });
    api.change.create.mockResolvedValue({ id: "b1", name: "x", payload: { tool: "edit", model: "sale.order", domain: [], ids: [5], change: {}, hash: "h", check: null } });
    api.change.check.mockResolvedValue({ hash: "h", refused: "Refused by the money guard. Change it in Accounting.", records: [], counts: { ready: 0 }, limits: { cap: 500, batch: 50, pace_ms: 0 }, receipt: null });
    api.change.get.mockResolvedValue({ id: "b1", name: "x", payload: { tool: "edit", model: "sale.order", domain: [], ids: [5], change: {}, hash: "h", check: null, approval: null } });
    render(<ChangeRecords tool="edit" />);
    fireEvent.change(screen.getByTestId("change-ids"), { target: { value: "5" } });
    fireEvent.click(screen.getByTestId("change-check"));
    expect(await screen.findByText(/Refused by the money guard/)).toBeTruthy();
    expect(screen.getByTestId("change-run").hasAttribute("disabled")).toBe(true);
    expect(api.change.create.mock.calls[0][1]).toMatchObject({ tool: "edit", ids: [5] });
  });

  it("transitions: 17 ready / 3 blocked with Odoo's reason, run enabled by the receipt", async () => {
    api.change.buttons.mockResolvedValue({ record_types: [{ model: "sale.order", label: "Sales Order", buttons: [{ key: "confirm", label: "Confirm", money: false, effects: [] }] }] });
    const recs = [...Array(17)].map((_, i) => ({ id: i + 1, name: `S${i}`, verdict: "ready" })).concat([...Array(3)].map((_, i) => ({ id: 30 + i, name: `X${i}`, verdict: "blocked", reason: "Some orders are not in a state requiring confirmation." })));
    api.change.create.mockResolvedValue({ id: "b2", name: "x", payload: { tool: "transitions", model: "sale.order", domain: [], ids: [], change: {}, hash: "h", check: null } });
    api.change.get.mockResolvedValue({ id: "b2", name: "x", payload: { tool: "transitions", model: "sale.order", domain: [], ids: [], change: {}, hash: "h", check: null, approval: null } });
    api.change.check.mockResolvedValue({ hash: "h", refused: null, records: recs, counts: { ready: 17, no_change: 0, blocked: 3 }, limits: { cap: 500, batch: 50, pace_ms: 0 }, receipt: "r", also: ["Odoo turns quotations into sales orders."], needs_approval: false });
    render(<ChangeRecords tool="transitions" />);
    await waitFor(() => expect(api.change.buttons).toHaveBeenCalled());
    fireEvent.click(screen.getByTestId("change-check"));
    expect(await screen.findByText(/17 ready · 0 nothing to change · 3 blocked/)).toBeTruthy();
    expect(screen.getAllByText(/not in a state requiring confirmation/)).toHaveLength(3);
    expect(screen.getByTestId("change-run").hasAttribute("disabled")).toBe(false);
  });

  it("ask: tax goes to Odoo's tax screen; a plan offers Fix it", async () => {
    api.upkeep.askStream.mockImplementation((id: string, t: string, onStep: (s: string) => void) => { onStep("Read 4 fields on 2 record types"); return api.upkeep.ask(id, t); });
    api.upkeep.guideTopics.mockResolvedValue({ topics: [] });
    api.upkeep.ask.mockResolvedValueOnce({ kind: "money", route: "Change taxes in Odoo: Accounting > Configuration > Taxes.", answer: "The suite doesn't change money settings. Change taxes in Odoo: Accounting > Configuration > Taxes." });
    render(<Ask />);
    fireEvent.change(screen.getByTestId("suite-ask-input"), { target: { value: "change VAT" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText(/Accounting > Configuration > Taxes/)).toBeTruthy();
    api.upkeep.ask.mockResolvedValueOnce({ kind: "plan", source: "plain code reader", dropped: [], plan: { record_type: "sale.order", label: "Sales Order", filters: [["state", "=", "sent"]], change: { tool: "transitions", button: "confirm" } } });
    api.upkeep.ticket.mockResolvedValue({ batch: { id: "b9" }, next: "/connections/c1/suite/change/transitions?batch=b9" });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    fireEvent.click(await screen.findByTestId("suite-fix-it"));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/connections/c1/suite/change/transitions?batch=b9"));
  });

  it("step builder and helpers turn plain fields into checked steps", () => {
    expect(buildStep("unit", { name: "Box of 6", reference: "Units", factor: "6" })).toEqual({ type: "units", inputs: { name: "Box of 6", reference: "Units", factor: 6 } });
    expect(typeof buildStep("unit", { name: "Box", factor: "0" })).toBe("string");
    expect(buildStep("product", { name: "Chair", price: "12", category: "All / Furniture" })).toEqual({ type: "create", inputs: { model: "product.template", values: { name: "Chair", list_price: 12, categ_id: { ref: "Furniture" } } } });
    expect(buildStep("setting", { field: "group_uom", value: "on" })).toEqual({ type: "setting", inputs: { values: { group_uom: true } } });
    expect(parseIds("#12, 15 15;x 18")).toEqual([12, 15, 18]);
    expect(bytes(38)).toBe("38 B");
  });

  it("record editor: paste parsing, values, view-only journal entries, held edits become a plan", async () => {
    const F = (name: string, label: string, type: string, editable = true) => ({ name, label, type, relation: null, required: false, stored: true, editable, why_not: editable ? null : "Odoo works this out itself.", sortable: true, groupable: true, choices: [] });
    const fields = [F("email", "Email", "char"), F("credit", "Credit", "monetary", false), F("is_company", "Is a Company", "boolean")];
    const out = parsePaste("id\tEmail\tCredit\tNope\n12\ta@x.test\t5\tz\n#13\tb@x.test\t6\tz", fields);
    expect(out.edits).toEqual([{ id: 12, field: "email", value: "a@x.test" }, { id: 13, field: "email", value: "b@x.test" }]);
    expect(out.problems.join(" ")).toMatch(/No field called 'Nope'.*'Credit' can't be edited/);
    expect(parsePaste("Email\nx", fields).edits).toHaveLength(0);
    expect(showValue([3, "Nigeria"])).toBe("Nigeria");
    expect(showValue(false, fields[2])).toBe("No");
    rec.models.mockResolvedValue({ models: [] });
    rec.meta.mockResolvedValue({ model: "res.partner", label: "Contact", fields, columns: ["email"], view_only: null, has_active: true });
    rec.search.mockResolvedValue({ total: 2, offset: 0, limit: 80, groups: null, rows: [{ id: 12, display_name: "Ada", email: "old@x.test" }, { id: 13, display_name: "Bo", email: "" }] });
    rec.plan.mockResolvedValue({ plan: { id: "p7" }, steps: 1, refused: [] });
    render(<RecordEditor />);
    const cell = await screen.findByTestId("cell-12-email");
    fireEvent.doubleClick(cell);
    const input = screen.getByLabelText("New Email");
    fireEvent.change(input, { target: { value: "new@x.test" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(await screen.findByText(/1 edits held, nothing written yet/)).toBeTruthy();
    fireEvent.click(screen.getByTestId("rec-make-plan"));
    await waitFor(() => expect(rec.plan).toHaveBeenCalledWith("c1", "res.partner", [{ id: 12, field: "email", value: "new@x.test" }], "Edit Contact"));
    expect(push).toHaveBeenCalledWith("/connections/c1/suite/setup?plan=p7&view=board");
  });
});
