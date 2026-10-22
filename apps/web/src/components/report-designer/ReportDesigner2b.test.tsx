import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const m = vi.hoisted(() => ({
  publish: vi.fn(),
  draft: vi.fn(),
  lines: vi.fn(),
  gallery: vi.fn(),
  emailList: vi.fn(),
  emailLoad: vi.fn(),
  emailCopy: vi.fn(),
  emailPreview: vi.fn(),
  emailSave: vi.fn(),
  compare: vi.fn(),
  visual: vi.fn(),
}));
vi.mock("@/lib/api", () => ({
  api: {
    reportEngineLoad: vi.fn(async () => ({
      major: 17, model: "account.move", reports: [{ id: 7, name: "Invoices", report_name: "account.report_invoice" }],
      report: { id: 7, name: "Invoices", report_name: "account.report_invoice", model: "account.move" },
      fields: { name: { string: "Number", type: "char" }, invoice_line_ids: { string: "Invoice lines", type: "one2many" }, partner_id: { string: "Customer", type: "many2one" } },
      records: [{ id: 3, display_name: "INV/1" }],
    })),
    layoutLoad: vi.fn(async () => ({
      major: 17, report: { id: 7, name: "Invoices", report_name: "account.report_invoice", model: "account.move" },
      document: { key: "d", view_id: 9 }, record_var: "o",
      slots: [{ id: "top", label: "Top of the document", xpath: "", position: "top" }, { id: "bottom", label: "Bottom of the document", xpath: "", position: "bottom" }],
      placements: [], earlier_changes: false, line_fields: ["invoice_line_ids"], layer: null,
      blocks: ["text", "heading", "line_table", "qr", "watermark"],
    })),
    variants: vi.fn(async () => ({ languages: [{ code: "fr_FR", name: "French", record_id: 4, note: null }], currencies: [], companies: [] })),
    linesFields: (...a: unknown[]) => m.lines(...a),
    layoutDraft: (...a: unknown[]) => m.draft(...a),
    layoutPublish: (...a: unknown[]) => m.publish(...a),
    layoutCompare: (...a: unknown[]) => m.compare(...a),
    layoutCompareVisual: (...a: unknown[]) => m.visual(...a),
    gallery: (...a: unknown[]) => m.gallery(...a),
    reportEngineProof: vi.fn(),
    reportEngineRevert: vi.fn(),
    emailList: (...a: unknown[]) => m.emailList(...a),
    emailLoad: (...a: unknown[]) => m.emailLoad(...a),
    emailCopy: (...a: unknown[]) => m.emailCopy(...a),
    emailPreview: (...a: unknown[]) => m.emailPreview(...a),
    emailSave: (...a: unknown[]) => m.emailSave(...a),
    emailRestore: vi.fn(),
    emailDelete: vi.fn(),
    blockSetList: vi.fn(async () => ({ sets: [] })),
  },
}));
const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

import { ReportDesignerShell } from "./ReportDesignerShell";

beforeEach(() => {
  Object.values(m).forEach((f) => f.mockReset());
  m.draft.mockResolvedValue({ ok: true, pages: 2, missing: [], checks: [{ kind: "split", level: "warning", page: 2, text: "split" }], content_base64: btoa("%PDF") });
  m.lines.mockResolvedValue({ field: "invoice_line_ids", columns: [
    { name: "price_subtotal", label: "Subtotal", type: "monetary", can_total: true },
    { name: "name", label: "Description", type: "text", can_total: false },
  ] });
  globalThis.URL.createObjectURL = vi.fn(() => "about:blank");
  globalThis.URL.revokeObjectURL = vi.fn();
});
afterEach(() => cleanup());

async function openPrints() {
  render(<ReportDesignerShell connectionId="c1" />);
  await waitFor(() => expect(screen.getByTestId("rd-record-pos")).toHaveTextContent("INV/1 (1 of 1)"));
  expect(await screen.findByLabelText("Bottom of the document")).toBeChecked();
}

describe("Report designer stage 2b", () => {
  it("compares before and after as page pictures with changes highlighted", async () => {
    m.compare.mockResolvedValue({ before_base64: btoa("%PDF"), after_base64: btoa("%PDF"), checks: [],
      diff: { same: false, pages_before: 1, pages_after: 1, pages: [{ page: 1, added: ["Hello"], removed: [] }] } });
    const page = { page: 1, width: 10, height: 14, before_png: "AA==", after_png: "AQ==", overlay_png: "Ag==", changed_percent: 3.2, only_in: null, summary: "Page 1: 3.2% of the page changed, near the top." };
    m.visual.mockResolvedValue({ visual: { pages: [page], same: false, page_counts: { published: 1, draft: 1 }, truncated: false }, diff: {} });
    await openPrints();
    fireEvent.click(screen.getByRole("button", { name: "Text" }));
    await waitFor(() => expect(screen.getByTestId("rd-compare")).not.toBeDisabled());
    fireEvent.click(screen.getByTestId("rd-compare"));
    expect(await screen.findByText(/added: Hello/)).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("rd-compare-pictures"));
    expect(await screen.findByText("Page 1: 3.2% of the page changed, near the top.")).toBeInTheDocument();
    expect(screen.getByAltText("Page 1 with changes highlighted")).toHaveAttribute("src", "data:image/png;base64,Ag==");
    expect(m.visual).toHaveBeenCalledWith("c1", expect.objectContaining({ report_id: 7, record_id: 3 }));
    fireEvent.click(screen.getByLabelText("Show before and after side by side"));
    expect(screen.getByAltText("Page 1 before")).toBeInTheDocument();
    expect(screen.getByAltText("Page 1 after")).toBeInTheDocument();
  });

  it("lines table with a totals row: pick lines and columns, then publish them in place", async () => {
    m.publish.mockRejectedValueOnce(new Error("stop"));
    await openPrints();
    fireEvent.click(screen.getByRole("button", { name: "Lines table" }));
    expect(screen.getByTestId("rd-publish")).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Lines, block 1"), { target: { value: "invoice_line_ids" } });
    const cols = await screen.findByLabelText("Columns, block 1");
    fireEvent.click(within(cols).getByLabelText("Description"));
    fireEvent.click(within(cols).getByLabelText("Subtotal"));
    fireEvent.click(within(cols).getByLabelText("total"));
    fireEvent.change(screen.getByLabelText("Totals label, block 1"), { target: { value: "Total due" } });
    fireEvent.click(screen.getByTestId("rd-publish"));
    await waitFor(() => expect(m.publish).toHaveBeenCalled());
    expect(m.publish.mock.calls[0][1]).toEqual({
      report_id: 7, record_id: 3,
      placements: [{ slot: "bottom", blocks: [{ type: "line_table", field: "invoice_line_ids", totals_label: "Total due", columns: [
        { field: "name", label: "Description", sum: false },
        { field: "price_subtotal", label: "Subtotal", sum: true },
      ] }] }],
    });
  });

  it("conditional block in plain words, and the draft's page checks", async () => {
    await openPrints();
    fireEvent.click(screen.getByRole("button", { name: "Text" }));
    fireEvent.click(screen.getByRole("button", { name: "Only show when…" }));
    fireEvent.change(screen.getByLabelText("Only when field, block 1"), { target: { value: "partner_id" } });
    fireEvent.click(screen.getByRole("button", { name: "Set" }));
    expect(screen.getByText(/Only when Customer is filled in/)).toBeInTheDocument();
    await waitFor(() => expect(m.draft).toHaveBeenCalled(), { timeout: 3000 });
    expect(m.draft.mock.calls.at(-1)?.[1].placements[0].blocks[0].condition).toEqual({ match: "all", rules: [{ field: "partner_id", op: "set" }] });
    await waitFor(() => expect(screen.getByTestId("rd-checks")).toHaveTextContent("A table of lines is split across pages (page 2)"));
  });

  it("language preview prints the draft for a record in that language", async () => {
    await openPrints();
    fireEvent.change(await screen.findByLabelText("Language, currency or company"), { target: { value: "lang:fr_FR" } });
    await waitFor(() => expect(m.draft).toHaveBeenCalled(), { timeout: 3000 });
    expect(m.draft.mock.calls.at(-1)?.[1]).toEqual(expect.objectContaining({ record_id: 4, lang: "fr_FR", placements: [] }));
  });

  it("starter gallery fills the layout", async () => {
    m.gallery.mockResolvedValue({ major: 17, starters: [{ key: "draft_watermark", label: "DRAFT watermark until posted", placements: [{ slot: "bottom", blocks: [{ type: "watermark", text: "DRAFT", colour: "grey" }] }] }] });
    await openPrints();
    fireEvent.click(screen.getByRole("button", { name: "Start from a template…" }));
    fireEvent.click(await screen.findByRole("button", { name: "DRAFT watermark until posted" }));
    expect((screen.getByLabelText("Watermark text 1") as HTMLInputElement).value).toBe("DRAFT");
    expect(screen.getByTestId("rd-publish")).toHaveTextContent("Publish changes (1)");
  });

  it("emails: copy Odoo's template first, add a block, preview at computer and phone width, save", async () => {
    m.emailList.mockResolvedValue({ templates: [{ id: 11, name: "Invoice: Sending", subject: "Invoice", ingenium_copy: false, copied_from: null }] });
    const base = { template: { id: 11, name: "Invoice: Sending", subject: "Invoice", model: "account.move" }, slots: [{ id: "top", label: "Top of the email", xpath: "", position: "top" }, { id: "bottom", label: "Bottom of the email", xpath: "", position: "bottom" }], blocks: ["text", "heading"], line_fields: [], fields: { name: { string: "Number", type: "char" } }, records: [{ id: 3, display_name: "INV/1" }], placements: [] };
    m.emailLoad.mockResolvedValueOnce({ ...base, editable: false }).mockResolvedValue({ ...base, template: { ...base.template, id: 12 }, editable: true });
    m.emailCopy.mockResolvedValue({ ok: true, template_id: 12, item_id: "x" });
    m.emailPreview.mockResolvedValue({ subject: "Invoice INV/1", html: "<p>Hello</p>", widths: { desktop: 600, phone: 375 } });
    m.emailSave.mockResolvedValue({ ok: true, previous_body: "<p>old</p>", subject: "Invoice INV/1", html: "<p>Hello</p>", widths: { desktop: 600, phone: 375 } });
    await openPrints();
    fireEvent.click(screen.getByRole("tab", { name: "Emails" }));
    fireEvent.click(await screen.findByRole("button", { name: "Invoice: Sending" }));
    fireEvent.click(await screen.findByRole("button", { name: "Make a copy" }));
    await waitFor(() => expect(m.emailCopy).toHaveBeenCalledWith("c1", 11));
    fireEvent.click(await screen.findByRole("button", { name: "Text" }));
    fireEvent.change(screen.getByLabelText("Text 1"), { target: { value: "Thanks!" } });
    await waitFor(() => expect(screen.getByTitle("Email in iPhone Mail")).toBeInTheDocument(), { timeout: 3000 });
    expect(m.emailPreview.mock.calls.at(-1)?.[1]).toEqual({ template_id: 12, record_id: 3, highlight: null, placements: [{ slot: "bottom", blocks: [{ type: "text", text: "Thanks!" }] }] });
    expect(screen.getByTitle("Email in Gmail")).toHaveStyle({ width: "600px" });
    fireEvent.click(screen.getByTestId("em-save"));
    await waitFor(() => expect(m.emailSave).toHaveBeenCalledWith("c1", { template_id: 12, record_id: 3, placements: [{ slot: "bottom", blocks: [{ type: "text", text: "Thanks!" }] }] }));
  });
});
