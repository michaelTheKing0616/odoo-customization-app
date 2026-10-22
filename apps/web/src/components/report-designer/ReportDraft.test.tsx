import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const m = vi.hoisted(() => ({ draft: vi.fn() }));
vi.mock("@/lib/api", () => ({
  api: {
    reportEngineLoad: vi.fn(async () => ({
      major: 18, model: "account.move", reports: [{ id: 7, name: "Invoice", report_name: "account.report_invoice" }],
      report: { id: 7, name: "Invoice", report_name: "account.report_invoice", model: "account.move" },
      slots: [{ id: "bottom", label: "Bottom of the page", xpath: "//x", position: "after" }],
      fields: { name: { string: "Number", type: "char" } },
      records: [{ id: 3, display_name: "INV/1" }],
    })),
    layoutLoad: vi.fn(async () => ({
      major: 18, report: { id: 7, name: "Invoice", report_name: "account.report_invoice", model: "account.move" },
      document: { key: "d", view_id: 9 }, record_var: "o", slots: [{ id: "bottom", label: "Bottom of the page", xpath: "", position: "bottom" }],
      placements: [], earlier_changes: false, line_fields: [], layer: null, blocks: ["text"],
    })),
    variants: vi.fn(async () => ({ languages: [], currencies: [], companies: [] })),
    layoutDraft: (...a: unknown[]) => m.draft(...a),
    reportEngineProof: vi.fn(),
    reportEnginePublish: vi.fn(),
    reportEngineRevert: vi.fn(),
  },
}));
vi.mock("sonner", () => ({ toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }) }));

import { ReportDesignerShell } from "./ReportDesignerShell";

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  m.draft.mockReset();
  globalThis.URL.createObjectURL = vi.fn(() => "blob:pdf");
  globalThis.URL.revokeObjectURL = vi.fn();
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("Report draft proof", () => {
  it("waits 1.2 s after the last edit, cancels older requests, keeps the last good PDF", async () => {
    let first: (v: unknown) => void = () => undefined;
    m.draft
      .mockImplementationOnce((_id: string, _b: unknown, signal: AbortSignal) => new Promise((res) => { first = res; signal.addEventListener("abort", () => res(null)); }))
      .mockResolvedValueOnce({ ok: true, pages: 1, missing: [], checks: [], content_base64: btoa("%PDF-1.4") });
    render(<ReportDesignerShell connectionId="c1" />);
    await act(async () => { await vi.advanceTimersByTimeAsync(10); });
    fireEvent.click(screen.getByRole("button", { name: "Text" }));
    const box = await screen.findByRole("textbox", { name: /text/i }).catch(() => screen.getAllByRole("textbox").at(-1)!);
    fireEvent.change(box, { target: { value: "Thanks" } });
    await act(async () => { await vi.advanceTimersByTimeAsync(600); });
    fireEvent.change(box, { target: { value: "Thanks for your order" } });
    await act(async () => { await vi.advanceTimersByTimeAsync(1100); });
    expect(m.draft).not.toHaveBeenCalled();
    await act(async () => { await vi.advanceTimersByTimeAsync(200); });
    expect(m.draft).toHaveBeenCalledTimes(1);
    expect(m.draft.mock.calls[0][1]).toEqual({ report_id: 7, record_id: 3, placements: [{ slot: "bottom", blocks: [{ type: "text", text: "Thanks for your order" }] }], lang: null, company_id: null, published_pages: null });
    expect(screen.getByTestId("rd-updating")).toHaveTextContent("Updating the report preview…");
    // A newer edit supersedes the request in flight.
    fireEvent.change(box, { target: { value: "Thanks!" } });
    await act(async () => { await vi.advanceTimersByTimeAsync(1300); });
    expect((m.draft.mock.calls[0][2] as AbortSignal).aborted).toBe(true);
    first(null);
    await act(async () => { await vi.advanceTimersByTimeAsync(10); });
    expect(screen.getByTestId("rd-proof-pages")).toHaveTextContent("1 page, printed by Odoo, draft, only you see it");
  });
});
