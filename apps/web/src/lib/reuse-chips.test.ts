import { describe, expect, it } from "vitest";
import {
  autoWiredReuseDecisions,
  confirmedReuseModelsFromDraft,
  inferredReuseSuggestions,
  installableReuseSuggestions,
} from "./reuse-chips";

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

describe("reuse suggestion filters", () => {
  const draft = {
    reuse: {
      plan: {
        decisions: [
          { model: "sale.order", source: "inferred", confirmed: false, reason: "prompt" },
          { model: "account.move", source: "installable", confirmed: false, module: "account" },
          {
            model: "res.partner",
            source: "apply_readiness",
            confirmed: true,
            link_only: true,
          },
          { model: "crm.lead", source: "inferred", confirmed: false },
        ],
      },
    },
  };

  it("splits inferred, installable, and auto-wired without promoting connection rows", () => {
    expect(inferredReuseSuggestions(draft, ["crm.lead"]).map((d) => d.model)).toEqual([
      "sale.order",
    ]);
    expect(installableReuseSuggestions(draft).map((d) => d.model)).toEqual(["account.move"]);
    expect(autoWiredReuseDecisions(draft).map((d) => d.model)).toEqual(["res.partner"]);
  });
});
