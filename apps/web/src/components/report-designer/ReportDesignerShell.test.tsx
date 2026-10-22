import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const publish = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    reportEngineLoad: vi.fn(async () => ({
      major: 18,
      model: "account.move",
      reports: [{ id: 7, name: "Invoices", report_name: "account.report_invoice" }],
      report: { id: 7, name: "Invoices", report_name: "account.report_invoice", model: "account.move" },
      slots: [
        { id: "top", label: "Top of the document", xpath: "//div[hasclass('page')]", position: "before" },
        { id: "bottom", label: "Bottom of the document", xpath: "//div[hasclass('page')]", position: "inside" },
      ],
      fields: { name: { string: "Number", type: "char" } },
      records: [{ id: 3, display_name: "INV/2026/0001" }],
    })),
    layoutLoad: vi.fn(async () => ({
      major: 18, report: { id: 7, name: "Invoices", report_name: "account.report_invoice", model: "account.move" },
      document: { key: "account.report_invoice_document", view_id: 9 }, record_var: "o",
      slots: [
        { id: "top", label: "Top of the document", xpath: "", position: "top" },
        { id: "bottom", label: "Bottom of the document", xpath: "", position: "bottom" },
      ],
      placements: [], earlier_changes: false, line_fields: ["invoice_line_ids"], layer: null,
      blocks: ["text", "heading", "field", "line_table"],
    })),
    variants: vi.fn(async () => ({ languages: [], currencies: [], companies: [] })),
    reportEngineProof: vi.fn(),
    layoutPublish: (...args: unknown[]) => publish(...args),
    reportEngineRevert: vi.fn(),
  },
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { ReportDesignerShell } from "./ReportDesignerShell";

afterEach(() => cleanup());

describe("ReportDesignerShell", () => {
  it("adds a footer text block and publishes it to the chosen slot", async () => {
    publish.mockRejectedValueOnce(new Error("stop"));
    render(<ReportDesignerShell connectionId="1" />);
    await waitFor(() => expect(screen.getByTestId("rd-record-pos")).toHaveTextContent("INV/2026/0001 (1 of 1)"));
    expect(await screen.findByLabelText("Bottom of the document")).toBeChecked();
    const publishBtn = screen.getByTestId("rd-publish");
    expect(publishBtn).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Text" }));
    fireEvent.change(screen.getByLabelText("Text 1"), { target: { value: "Thank you" } });
    expect(publishBtn).toHaveTextContent("Publish changes (1)");
    fireEvent.click(publishBtn);
    await waitFor(() =>
      expect(publish).toHaveBeenCalledWith("1", { report_id: 7, record_id: 3, placements: [{ slot: "bottom", blocks: [{ type: "text", text: "Thank you" }] }] }),
    );
  });
});
