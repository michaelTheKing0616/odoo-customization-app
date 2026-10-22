import { describe, expect, it } from "vitest";
import { tryPlaceholder } from "./ModelExplorer";

describe("tryPlaceholder (touch 96)", () => {
  it("prefers a real custom model", () => {
    expect(tryPlaceholder([{ model: "res.partner", label: "Contact" }, { model: "x_fleet", label: "Fleet" }])).toBe("Try: Fleet");
  });
  it("falls back to a business model, skipping technical ones", () => {
    expect(tryPlaceholder([{ model: "ir.model", label: "Models" }, { model: "sale.order", label: "Sales Order" }])).toBe("Try: Sales Order");
  });
  it("plain hint when empty", () => {
    expect(tryPlaceholder([])).toBe("Search models");
  });
});
