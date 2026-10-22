import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { InsightResult } from "./Insights";

describe("Look closer results", () => {
  afterEach(cleanup);
  it("renders rows as a table, notes as sentences, and never raw JSON or codes", () => {
    render(<InsightResult data={{ record_type: "Contact", code: "res.partner", records: 12, note: "Only fields Odoo tracks appear here.",
      blocked: [{ id: 7, name: "Gap Idle", because: ["1 open sales orders"] }], safe: [] }} />);
    expect(screen.getByText("Only fields Odoo tracks appear here.")).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Because" })).toBeTruthy();
    expect(screen.getByText("1 open sales orders")).toBeTruthy();
    expect(screen.getByText("Nothing found.")).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/res\.partner|[{}]/);
  });
});
