import { describe, expect, it } from "vitest";
import {
  PAGE_DESCRIPTION,
  PLAN_STATUS_META,
  PRIMARY_CTA,
  SIGN_OFF_NOTE,
  approveGate,
  approverSlots,
  blockerLines,
  confirmCopy,
  countActionable,
  decideFailure,
  decisionRecordedMessage,
  emptyInboxGuide,
  expiryAbsolute,
  expiryPhrase,
  isPlanExpired,
  loadErrorGuide,
  noConnectionGuide,
  notFoundGuide,
  planDisplayStatus,
  riskCaution,
  riskMeaning,
  sanitizePlanInboxCopy,
  shortFingerprint,
  sortPlans,
  statusGuide,
  stepStates,
  timelineSteps,
  type InboxPlanCard,
  type PlanDisplayStatus,
} from "@/lib/planInboxScreen";

const NOW = new Date("2026-10-05T20:00:00Z");

function plan(overrides: Partial<InboxPlanCard> = {}): InboxPlanCard {
  return {
    plan_hash: "9c41e07ab2d35f18",
    schema_fp: "sfp_1",
    goal: "Give billing clerks the Billing group",
    status: "pending",
    max_risk: "R3",
    environment: "production",
    expires_at: "2026-10-06T19:00:00+00:00",
    requester_id: "usr_tunde",
    approvals: [],
    risk: { max: "R3", per_op: ["R3"], policy: { allow: true, approvers: 1, deny: false } },
    ...overrides,
  };
}

function allCopy(): string[] {
  const guides = [
    noConnectionGuide(),
    emptyInboxGuide("conn-1"),
    loadErrorGuide(),
    notFoundGuide("abc"),
  ];
  const statuses: PlanDisplayStatus[] = ["approved", "denied", "stopped", "voided", "stale", "expired", "blocked", "unknown"];
  for (const status of statuses) {
    const guide = statusGuide(plan(), status, NOW);
    if (guide) guides.push(guide);
  }
  for (const code of [null, 403, 404, 409, 422, 500]) {
    guides.push(decideFailure(code).guide);
  }
  guides.push(decideFailure(409, "frozen").guide, decideFailure(403, "the requester cannot approve this risk").guide);
  return [
    PAGE_DESCRIPTION,
    PRIMARY_CTA,
    SIGN_OFF_NOTE,
    ...Object.values(PLAN_STATUS_META).map((m) => m.label),
    ...guides.flatMap((g) => [g.title, g.why, g.next]),
    ...(["approve", "deny", "deny_and_stop"] as const).flatMap((d) => Object.values(confirmCopy(plan(), d, NOW))),
  ];
}

describe("planInboxScreen copy", () => {
  it("never uses em or en dashes, Oops, or slop verbs", () => {
    for (const line of allCopy()) {
      expect(line).not.toMatch(/[\u2014\u2013]/);
      expect(line).not.toMatch(/\b(oops|seamless|elevate|leverage|unleash)\b/i);
    }
  });

  it("says approve is a signature and Odoo changes only at executor apply", () => {
    expect(PAGE_DESCRIPTION).toMatch(/Odoo changes only when the executor applies it/);
    expect(SIGN_OFF_NOTE).toMatch(/Nothing is written to Odoo from this page/);
    expect(PLAN_STATUS_META.approved.label).toBe("Approved, not applied");
  });

  it("shows amber caution only for open R3 and R4 cards", () => {
    expect(riskCaution(plan(), "pending")?.title).toBe("R3 on production");
    expect(riskCaution(plan({ max_risk: "R1" }), "pending")).toBeNull();
    expect(riskCaution(plan({ max_risk: "R2" }), "pending")).toBeNull();
    expect(riskCaution(plan(), "approved")).toBeNull();
    expect(
      riskCaution(plan({ max_risk: "R4", risk: { policy: { approvers: 2 } } }), "pending")?.title,
    ).toBe("Heavy R4 on production");
  });

  it("writes one honest line per timeline step", () => {
    const pending = timelineSteps(plan(), "pending");
    expect(pending.map((s) => s.state)).toEqual(["done", "current", "todo"]);
    expect(pending[1].detail).toBe("0 of 1 signature");
    expect(pending[2].detail).toMatch(/never from this page/);
    const approved = timelineSteps(plan({ status: "approved" }), "approved");
    expect(approved[2].detail).toMatch(/Rechecks fingerprint/);
    for (const step of [...pending, ...approved]) expect(step.detail).not.toMatch(/[\u2014\u2013]/);
  });

  it("sanitizes dashes", () => {
    expect(sanitizePlanInboxCopy("a \u2014 b \u2013 c")).toBe("a - b - c");
  });
});

describe("planDisplayStatus", () => {
  it("maps engine statuses", () => {
    expect(planDisplayStatus(plan(), NOW)).toBe("pending");
    expect(planDisplayStatus(plan({ status: "approved" }), NOW)).toBe("approved");
    expect(planDisplayStatus(plan({ status: "voided" }), NOW)).toBe("voided");
    expect(planDisplayStatus(plan({ status: "denied" }), NOW)).toBe("denied");
    expect(planDisplayStatus(plan({ status: "stopped" }), NOW)).toBe("stopped");
    expect(planDisplayStatus(plan({ status: "weird" }), NOW)).toBe("unknown");
  });

  it("expires pending and approved cards at or after expires_at", () => {
    expect(planDisplayStatus(plan({ expires_at: "2026-10-05T20:00:00+00:00" }), NOW)).toBe("expired");
    expect(planDisplayStatus(plan({ status: "approved", expires_at: "2026-10-05T10:00:00Z" }), NOW)).toBe("expired");
    expect(isPlanExpired({ expires_at: "" }, NOW)).toBe(true);
    expect(isPlanExpired({ expires_at: "nonsense" }, NOW)).toBe(true);
  });

  it("marks stale over everything and hard-stop R4 as blocked", () => {
    expect(planDisplayStatus(plan(), NOW, { stale: true })).toBe("stale");
    expect(
      planDisplayStatus(plan({ max_risk: "R4", risk: { policy: { deny: true, approvers: 0 } } }), NOW),
    ).toBe("blocked");
  });
});

describe("approverSlots", () => {
  it("R3 has one slot from policy", () => {
    const slots = approverSlots(plan());
    expect(slots.needed).toBe(1);
    expect(slots.slots).toEqual([{ index: 1, person: null }]);
    expect(slots.distinctRequired).toBe(false);
  });

  it("production heavy R4 has two slots and one person fills one", () => {
    const card = plan({
      max_risk: "R4",
      risk: { policy: { allow: true, approvers: 2, needs_backup: true } },
      approvals: [
        { approver_id: "a", user_id: "usr_kemi", decision: "approve" },
        { approver_id: "b", user_id: "usr_kemi", decision: "approve" },
        { approver_id: "c", user_id: "usr_x", decision: "deny" },
      ],
    });
    const slots = approverSlots(card);
    expect(slots.needed).toBe(2);
    expect(slots.distinctRequired).toBe(true);
    expect(slots.slots).toEqual([
      { index: 1, person: "usr_kemi" },
      { index: 2, person: null },
    ]);
  });
});

describe("approveGate", () => {
  it("allows a signed-in viewer on a pending card with a schema fingerprint", () => {
    expect(approveGate(plan(), NOW, "usr_amaka")).toEqual({ allowed: true, reason: null });
  });

  it("blocks signed-out viewers, missing schema fingerprints, and closed cards", () => {
    expect(approveGate(plan(), NOW, null).reason?.title).toBe("Sign in to approve");
    expect(approveGate(plan({ schema_fp: "" }), NOW, "u").reason?.title).toMatch(/no schema fingerprint/);
    expect(approveGate(plan({ status: "approved" }), NOW, "u").allowed).toBe(false);
    expect(approveGate(plan(), NOW, "u", { stale: true }).reason?.title).toMatch(/fingerprint changed/);
  });

  it("stops the same person filling both heavy R4 slots", () => {
    const card = plan({
      max_risk: "R4",
      risk: { policy: { allow: true, approvers: 2 } },
      approvals: [{ user_id: "usr_kemi", approver_id: "usr_kemi", decision: "approve" }],
    });
    expect(approveGate(card, NOW, "usr_kemi").reason?.title).toBe("You already approved this fingerprint");
    expect(approveGate(card, NOW, "usr_amaka").allowed).toBe(true);
  });
});

describe("decideFailure", () => {
  it("never says forbidden for a missing plan", () => {
    const failure = decideFailure(404, "not found");
    expect(failure.kind).toBe("not_found");
    expect(failure.guide.title).toBe("Plan not found");
    expect(JSON.stringify(failure.guide)).not.toMatch(/forbidden/i);
  });

  it("maps stale, frozen, requester, network", () => {
    expect(decideFailure(409, "plan_stale").kind).toBe("stale");
    expect(decideFailure(409, "frozen").kind).toBe("frozen");
    expect(decideFailure(403, "the requester cannot approve this risk").guide.title).toMatch(/requester/);
    expect(decideFailure(403).guide.title).toMatch(/role/);
    expect(decideFailure(null).kind).toBe("network");
    expect(decideFailure(500).guide.why).toMatch(/500/);
  });
});

describe("helpers", () => {
  it("sorts actionable plans first and counts them", () => {
    const a = plan({ plan_hash: "a", status: "approved" });
    const b = plan({ plan_hash: "b" });
    const c = plan({ plan_hash: "c", status: "voided" });
    const d = plan({ plan_hash: "d" });
    expect(sortPlans([a, b, c, d], NOW).map((p) => p.plan_hash)).toEqual(["b", "d", "a", "c"]);
    expect(countActionable([a, b, c, d], NOW)).toBe(2);
  });

  it("phrases expiry both ways", () => {
    expect(expiryPhrase({ expires_at: "2026-10-06T19:00:00+00:00" }, NOW)).toBe("Expires in 23 hours");
    expect(expiryPhrase({ expires_at: "2026-10-05T17:00:00Z" }, NOW)).toBe("Expired 3 hours ago");
    expect(expiryPhrase({ expires_at: "2026-10-12T20:00:00Z" }, NOW)).toBe("Expires in 7 days");
    expect(expiryAbsolute({ expires_at: "2026-10-06T19:00:00+00:00" }, { timeZone: "Africa/Lagos" })).toMatch(/20:00/);
  });

  it("names risk, fingerprint, blockers, steps", () => {
    expect(riskMeaning("R3")).toMatch(/Security/);
    expect(shortFingerprint("9c41e07ab2d35f18")).toBe("9c41e07ab2d3");
    expect(blockerLines(plan({ r3_blockers: ["not_heavy_r4", "backup", "odd_thing"] }))).toEqual([
      "No backup id is recorded on the card.",
      "odd thing",
    ]);
    expect(stepStates("pending")).toEqual(["done", "current", "todo"]);
    expect(stepStates("approved")).toEqual(["done", "done", "current"]);
    expect(stepStates("expired")).toEqual(["done", "blocked", "todo"]);
  });

  it("reports recorded decisions honestly", () => {
    const heavy = plan({
      max_risk: "R4",
      risk: { policy: { allow: true, approvers: 2 } },
      approvals: [{ user_id: "usr_kemi", decision: "approve" }],
    });
    expect(decisionRecordedMessage(heavy, "approve", NOW)).toBe("Approval recorded. 1 of 2 approvals.");
    expect(decisionRecordedMessage(plan({ status: "approved" }), "approve", NOW)).toMatch(/^Approved\. Not applied yet\./);
    expect(decisionRecordedMessage(plan({ status: "denied" }), "deny", NOW)).toMatch(/cannot be applied/);
  });
});
