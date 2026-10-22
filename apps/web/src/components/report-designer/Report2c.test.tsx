import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const m = vi.hoisted(() => ({ brandCompanies: vi.fn(), brandCopy: vi.fn(), brandUndo: vi.fn(), emailAppChecks: vi.fn(), reportFromDocument: vi.fn(), presets: vi.fn(async () => ({ presets: [] })), presetSave: vi.fn(), presetApply: vi.fn(), emailTestSend: vi.fn() }));
vi.mock("@/lib/api", () => ({
  api: Object.fromEntries(Object.keys(m).map((k) => [k, (...a: unknown[]) => (m as Record<string, (...x: unknown[]) => unknown>)[k](...a)])),
}));
const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

import { CompanyBrands, EmailAppChecks } from "./Report2c";

afterEach(() => cleanup());

describe("Report and email designer stage 2c", () => {
  it("copies one company's style to another", async () => {
    m.brandCompanies.mockResolvedValue({ note: "", companies: [
      { id: 1, name: "Main Co", primary_color: "#0F766E", font: "Lato", external_report_layout_id: [5, "Standard"], can_undo: false },
      { id: 2, name: "Second Co", primary_color: false, font: false, external_report_layout_id: false, can_undo: true },
    ] });
    m.brandCopy.mockResolvedValue({ results: [{ company_id: 2, ok: true }], copied: {} });
    render(<CompanyBrands connectionId="c1" />);
    fireEvent.click(screen.getByText("Branding per company…"));
    await screen.findAllByText("Main Co");
    fireEvent.click(screen.getAllByLabelText(/Copy from/)[0]);
    fireEvent.click(screen.getAllByLabelText(/to/)[1]);
    fireEvent.click(screen.getByText("Copy the style"));
    await waitFor(() => expect(m.brandCopy).toHaveBeenCalledWith("c1", 1, [2]));
    expect(screen.getByText("Undo")).toBeTruthy();
  });

  it("email checks list findings by app and offer a dark preview", async () => {
    m.emailAppChecks.mockResolvedValue({ findings: [{ severity: "high", apps: "Outlook on Windows", text: "The layout uses flexible boxes.", fix: "Use simple tables for columns." }],
      score: 80, size_kb: 4.2, summary: "1 thing to check before sending.", checked: "rendered for one record", html: null, note: "Checks only." });
    render(<EmailAppChecks connectionId="c1" templateId={7} recordId={3} html="<p>Hi</p>" />);
    fireEvent.click(screen.getByText("Check in email apps"));
    expect(await screen.findByText(/flexible boxes/)).toBeTruthy();
    expect(m.emailAppChecks).toHaveBeenCalledWith("c1", 7, 3);
    fireEvent.click(screen.getByText("Dark mode preview"));
    expect(screen.getByTitle("Email in dark mode")).toBeTruthy();
  });
});
