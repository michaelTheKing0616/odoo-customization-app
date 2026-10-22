import { describe, expect, it } from "vitest";
import type { BillingPlansCatalog, EntitlementsOut } from "@/lib/api";
import {
  billingErrorGuide,
  chargeEstimate,
  chooserTiers,
  entitlementRows,
  featureValue,
  formatUsd,
  nextTier,
  planDisplayName,
  primaryAction,
  riskNotices,
  sanitizeBillingCopy,
  slotMeter,
  statusMeta,
  tierLadder,
} from "./billingScreen";

// Mirrors apps/api/app/entitlements.py PLAN_PRICING (real list prices only).
const CATALOG: BillingPlansCatalog = {
  tier_order: ["free_solo", "pro", "business", "agency"],
  display_features: [
    { key: "active_projects_limit", label: "Active projects" },
    { key: "designer", label: "View designer" },
    { key: "bulk_suite", label: "Bulk suite" },
    { key: "dev_tools", label: "Code Studio & developer tools" },
  ],
  project_pass: { display_name: "Project Pass", one_time_usd: 299 },
  plans: [
    { id: "free_solo", display_name: "Free Solo", monthly_usd: 0, extra_slot_monthly_usd: null, features: { active_projects_limit: "1", designer: "false", bulk_suite: "false", dev_tools: "false" } },
    { id: "pro", display_name: "Pro", monthly_usd: 39, extra_slot_monthly_usd: 15, features: { active_projects_limit: "3", designer: "true", bulk_suite: "false", dev_tools: "false" } },
    { id: "business", display_name: "Business", monthly_usd: 149, extra_slot_monthly_usd: 10, features: { active_projects_limit: "10", designer: "true", bulk_suite: "true", dev_tools: "true" } },
    { id: "agency", display_name: "Agency", monthly_usd: 399, extra_slot_monthly_usd: null, features: { active_projects_limit: "25", designer: "true", bulk_suite: "true", dev_tools: "true" } },
  ],
};

const NOW = Date.parse("2026-10-05T12:00:00Z");
const ent = (over: Partial<EntitlementsOut> = {}): EntitlementsOut => ({
  workspace_id: "ws",
  plan_id: "pro",
  subscription_status: "active",
  features: CATALOG.plans[1].features,
  extra_project_slots: 0,
  active_projects: 1,
  active_project_limit: 3,
  trial_ends_at: null,
  current_period_end: "2026-10-29T00:00:00Z",
  ...over,
});

describe("billing copy", () => {
  it("never ships em or en dashes", () => {
    expect(sanitizeBillingCopy("Thanks — synced – soon")).not.toMatch(/[—–]/);
  });

  it("formats real prices with tabular-friendly USD", () => {
    expect(formatUsd(39, { whole: true })).toBe("$39");
    expect(formatUsd(69)).toBe("$69.00");
    expect(formatUsd(null)).toBe("Unavailable");
  });

  it("names plans from the catalog, falling back to known ids", () => {
    expect(planDisplayName("business", CATALOG)).toBe("Business");
    expect(planDisplayName("internal", null)).toBe("Internal");
  });

  it("maps Stripe statuses to plain labels and tones", () => {
    expect(statusMeta("past_due")).toMatchObject({ label: "Payment failed", tone: "danger" });
    expect(statusMeta("trialing").label).toBe("Trial");
    expect(statusMeta("active").tone).toBe("success");
  });
});

describe("primary action: Manage plan", () => {
  it("opens the Stripe portal for a paid plan", () => {
    expect(primaryAction("pro", "active", CATALOG)).toMatchObject({ kind: "portal", label: "Manage plan" });
  });
  it("opens the chooser for Free Solo and in-app trials (no Stripe customer)", () => {
    expect(primaryAction("free_solo", "active", CATALOG).kind).toBe("picker");
    expect(primaryAction("business", "trialing", CATALOG).kind).toBe("picker");
  });
  it("is disabled with a reason for internal workspaces", () => {
    const a = primaryAction("internal", "active", CATALOG);
    expect(a.kind).toBe("none");
    expect(a.hint).toMatch(/no Stripe subscription/);
  });
});

describe("charge estimate honesty", () => {
  it("adds purchased slots at the plan's real slot price", () => {
    const est = chargeEstimate(ent({ extra_project_slots: 2 }), CATALOG);
    expect(est.kind).toBe("scheduled");
    expect(est.total).toBe(39 + 2 * 15);
    expect(est.lines.map((l) => l.amount)).toEqual([39, 30]);
    expect(est.note).toMatch(/Stripe invoice is final/);
  });
  it("does not claim a scheduled charge during an in-app trial", () => {
    const est = chargeEstimate(ent({ plan_id: "business", subscription_status: "trialing", trial_ends_at: "2026-10-07T00:00:00Z" }), CATALOG);
    expect(est.heading).toBe("To keep Business");
    expect(est.note).toMatch(/nothing is scheduled/);
  });
  it("shows no estimate when list prices are missing", () => {
    const est = chargeEstimate(ent(), null);
    expect(est.kind).toBe("unknown");
    expect(est.total).toBeNull();
  });
  it("calls a past-due renewal an unpaid invoice, not a future charge", () => {
    const est = chargeEstimate(ent({ subscription_status: "past_due" }), CATALOG);
    expect(est.heading).toBe("Unpaid invoice");
    expect(est.dateLabel).toBe("Due since");
  });
  it("says internal is not billed", () => {
    expect(chargeEstimate(ent({ plan_id: "internal" }), CATALOG).heading).toBe("Not billed");
  });
  it("has no upcoming charge once canceled", () => {
    expect(chargeEstimate(ent({ subscription_status: "canceled" }), CATALOG).kind).toBe("none");
  });
});

describe("slot meter", () => {
  it("flags the limit only when reached", () => {
    expect(slotMeter(ent({ active_projects: 2 })).atLimit).toBe(false);
    const full = slotMeter(ent({ active_projects: 3 }));
    expect(full.atLimit).toBe(true);
    expect(full.hint).toMatch(/At your limit/);
  });
  it("points free plans to a paid tier instead of a slot", () => {
    expect(slotMeter(ent({ active_projects: 1, active_project_limit: 1 }), { slotsOffered: false }).hint).toMatch(/paid plan/);
  });
  it("handles unlimited plans", () => {
    expect(slotMeter(ent({ active_project_limit: null })).limit).toBeNull();
  });
});

describe("entitlements and tiers", () => {
  it("compares against the next tier and marks gains", () => {
    const next = nextTier(CATALOG, "pro");
    expect(next?.id).toBe("business");
    const rows = entitlementRows(CATALOG.plans[1].features, CATALOG, next);
    const bulk = rows.find((r) => r.key === "bulk_suite")!;
    expect(bulk.current.text).toBe("Not included");
    expect(bulk.next?.text).toBe("Included");
    expect(bulk.gain).toBe(true);
    expect(rows.find((r) => r.key === "dev_tools")!.label).toBe("Code Studio and developer tools");
  });
  it("has no next tier at the top", () => {
    expect(nextTier(CATALOG, "agency")).toBeNull();
  });
  it("lists only paid tiers in the chooser with gain counts", () => {
    const tiers = chooserTiers(CATALOG, "free_solo", CATALOG.plans[0].features, "active");
    expect(tiers.map((t) => t.id)).toEqual(["pro", "business", "agency"]);
    expect(tiers[0].cta).toBe("Continue with Pro");
    expect(tiers[0].delta).toMatch(/^Adds \d+ features?/);
  });
  it("offers Keep for the trial tier", () => {
    const tiers = chooserTiers(CATALOG, "business", CATALOG.plans[2].features, "trialing");
    expect(tiers.find((t) => t.id === "business")!.cta).toBe("Keep Business");
    expect(tiers.find((t) => t.id === "pro")!.delta).toMatch(/Drops/);
  });
  it("ladder marks the current plan with real prices", () => {
    const l = tierLadder(CATALOG, "pro");
    expect(l.map((t) => t.price)).toEqual([0, 39, 149, 399]);
    expect(l.find((t) => t.current)?.id).toBe("pro");
  });
  it("reads feature values in words", () => {
    expect(featureValue("unlimited").text).toBe("Unlimited");
    expect(featureValue("false").included).toBe(false);
    expect(featureValue("5").text).toBe("5");
  });
});

describe("risk notices only when something is at stake", () => {
  it("none for a healthy paid plan", () => {
    expect(riskNotices(ent(), CATALOG, NOW)).toEqual([]);
  });
  it("trial ending within 3 days", () => {
    const n = riskNotices(ent({ plan_id: "business", subscription_status: "trialing", trial_ends_at: "2026-10-07T12:00:00Z" }), CATALOG, NOW);
    expect(n).toHaveLength(1);
    expect(n[0]).toMatchObject({ id: "trial", tone: "warning" });
    expect(n[0].guide.title).toBe("Trial ends in 2 days");
  });
  it("no trial notice far from the end", () => {
    expect(riskNotices(ent({ subscription_status: "trialing", trial_ends_at: "2026-10-20T00:00:00Z" }), CATALOG, NOW)).toEqual([]);
  });
  it("payment failure is danger", () => {
    expect(riskNotices(ent({ subscription_status: "past_due" }), CATALOG, NOW)[0]).toMatchObject({ id: "payment", tone: "danger" });
  });
});

describe("error guides: what, why, next", () => {
  it("explains a missing Stripe customer without blame", () => {
    const g = billingErrorGuide("portal", "No billing customer on file");
    expect(g.title).toBe("No Stripe customer on file yet");
    expect(g.next).toMatch(/Manage plan/);
  });
  it("classifies admin-only refusals", () => {
    expect(billingErrorGuide("checkout", "Request failed (403)").title).toMatch(/admin/);
  });
  it("keeps raw detail for unknown failures", () => {
    expect(billingErrorGuide("portal", "boom").why).toMatch(/Detail: boom/);
  });
  it("never uses Oops or exclamation marks", () => {
    for (const ctx of ["portal", "checkout", "load"] as const) {
      const g = billingErrorGuide(ctx, "x");
      expect(`${g.title} ${g.why} ${g.next}`).not.toMatch(/Oops|!/);
    }
  });
});
