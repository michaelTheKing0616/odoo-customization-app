import { describe, expect, it } from "vitest";
import { automationStarters } from "./automationForm";

describe("automationStarters (touch 67)", () => {
  it("only uses models the database has, custom first, max three", () => {
    const s = automationStarters([
      { model: "res.partner", name: "Contact" },
      { model: "sale.order", name: "Sales Order" },
      { model: "x_fleet", name: "Fleet" },
      { model: "crm.lead", name: "Lead" },
    ]);
    expect(s.map((x) => x.model)).toEqual(["x_fleet", "sale.order", "crm.lead"]);
    expect(s[1].label).toBe("When a Sales Order is confirmed");
  });
  it("none when no known models", () => {
    expect(automationStarters([{ model: "ir.cron", name: "Cron" }])).toEqual([]);
  });
});
