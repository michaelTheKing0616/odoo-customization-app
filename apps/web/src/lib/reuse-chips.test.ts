import { describe, expect, it } from "vitest";
import { confirmedReuseModelsFromDraft } from "./reuse-chips";

describe("confirmedReuseModelsFromDraft", () => {
  it("keeps operator and installed rows, not auto-confirmed connection", () => {
    const chips = confirmedReuseModelsFromDraft({
      reuse: {
        plan: {
          decisions: [
            { model: "res.partner", source: "operator", confirmed: true },
            { model: "hr.expense", source: "installable", confirmed: true },
            { model: "sale.order", source: "connection", confirmed: true },
            { model: "crm.lead", source: "inferred", confirmed: false },
            { model: "purchase.order", source: "installable", confirmed: false },
          ],
        },
      },
    });
    expect(chips).toEqual(["res.partner", "hr.expense"]);
  });

  it("returns empty when the draft has no operator confirms", () => {
    expect(
      confirmedReuseModelsFromDraft({
        reuse: {
          plan: {
            decisions: [
              { model: "res.users", source: "connection", confirmed: true },
            ],
          },
        },
      }),
    ).toEqual([]);
  });
});
