"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { PlanInboxView, type PlanInboxPhase } from "@/components/plan-inbox/PlanInboxView";
import type { PlanDecisionState } from "@/components/plan-inbox/PlanLedger";
import {
  decideFailure,
  type InboxPlanCard,
  type PlanDecision,
  type PlanSection,
} from "@/lib/planInboxScreen";
import "@/components/plan-inbox/plan-inbox-operate.css";

/**
 * UI-S-50 vision harness. Fixtures only, no API. NEXT_PUBLIC_E2E=1.
 * Sections mirror the engine's nine copy sections (apps/api/app/changeset/plan_card.py).
 */

const NOW = new Date("2026-10-05T20:00:00Z");
const CONNECTION = "conn-lagos-retail";
const VIEWER = "usr_amaka";

function hoursFromNow(hours: number): string {
  return new Date(NOW.getTime() + hours * 3_600_000).toISOString().replace("Z", "+00:00");
}

type Seed = Omit<InboxPlanCard, "sections" | "connection_id"> & {
  assumptions: string[];
  undo: string[];
  verify: string[];
  notChanging: string[];
};

function sectionsFor(seed: Seed): PlanSection[] {
  const policy = seed.risk?.policy ?? {};
  const risk = [`max ${seed.max_risk}`, `per_op ${(seed.risk?.per_op ?? []).join(", ")}`];
  if (policy.deny) risk.push("denied");
  else {
    risk.push(`approvers ${policy.approvers}`);
    if (policy.needs_simulation) risk.push("needs simulation");
    if (policy.domain_owner) risk.push("needs domain owner");
    if (policy.needs_backup) risk.push("needs backup");
    if (policy.needs_window) risk.push("needs window");
  }
  const changes = (seed.changes ?? []).map((c) => c.description ?? c.type ?? "");
  return [
    { title: "goal and assumptions", body: [seed.goal, ...(seed.assumptions.length ? seed.assumptions : ["none"])].join("\n") },
    { title: "each change", body: changes.join("\n") || "none" },
    { title: "impact", body: `op_count ${(seed.changes ?? []).length}` },
    { title: "risk and why", body: risk.join("\n") },
    { title: "what is not changing", body: seed.notChanging.join("\n") || "none" },
    { title: "how it will be checked", body: seed.verify.join("\n") },
    { title: "how to undo", body: seed.undo.join("\n") || "none" },
    { title: "environment", body: seed.environment },
    { title: "plan fingerprint and expiry", body: `${seed.plan_hash}\n${seed.expires_at}` },
  ];
}

const HARNESS_ONLY = new Set(["assumptions", "undo", "verify", "notChanging"]);

function card(seed: Seed): InboxPlanCard {
  const rest = Object.fromEntries(
    Object.entries(seed).filter(([key]) => !HARNESS_ONLY.has(key)),
  ) as unknown as InboxPlanCard;
  return { ...rest, connection_id: CONNECTION, sections: sectionsFor(seed) };
}

const R3 = card({
  plan_hash: "9c41e07ab2d35f18",
  schema_fp: "sfp_4e1a90c2",
  goal: "Give the three billing clerks the Invoicing / Billing group",
  status: "pending",
  max_risk: "R3",
  environment: "production",
  expires_at: hoursFromNow(23),
  requester_id: "usr_tunde",
  approvals: [],
  risk: { max: "R3", per_op: ["R3", "R3", "R3"], policy: { allow: true, approvers: 1, deny: false } },
  changes: [
    { type: "user.groups.assign", description: "Add group account.group_account_invoice to user fola.adeyemi", params: { user: "fola.adeyemi", groups: ["account.group_account_invoice"] } },
    { type: "user.groups.assign", description: "Add group account.group_account_invoice to user chidi.okafor", params: { user: "chidi.okafor", groups: ["account.group_account_invoice"] } },
    { type: "user.groups.assign", description: "Add group account.group_account_invoice to user zainab.musa", params: { user: "zainab.musa", groups: ["account.group_account_invoice"] } },
  ],
  assumptions: ["The three users already exist and are active", "No user gets Billing Administrator"],
  notChanging: ["data.delete", "module.uninstall", "rpc.write"],
  verify: ["postcondition:user.groups.assign", "postcondition:user.groups.assign", "postcondition:user.groups.assign"],
  undo: ["user.groups.assign inverse user.groups.remove", "user.groups.assign inverse user.groups.remove", "user.groups.assign inverse user.groups.remove"],
});

const R1 = card({
  plan_hash: "1f7d2a6c90be4453",
  schema_fp: "sfp_77c1b0de",
  goal: "Rename the Sales menu to Orders",
  status: "pending",
  max_risk: "R1",
  environment: "staging",
  expires_at: hoursFromNow(24 * 6 + 20),
  requester_id: "usr_tunde",
  approvals: [],
  risk: { max: "R1", per_op: ["R1"], policy: { allow: true, approvers: 1, deny: false } },
  changes: [{ type: "menu.update", description: "Rename menu sale.sale_menu_root to Orders", params: { xmlid: "sale.sale_menu_root", name: "Orders" } }],
  assumptions: ["Only the label changes. The action and access stay the same."],
  notChanging: ["data.delete", "module.uninstall", "rpc.write"],
  verify: ["postcondition:menu.update"],
  undo: ["menu.update inverse menu.update"],
});

const R4 = card({
  plan_hash: "b8e2c4417a0f9d36",
  schema_fp: "sfp_c90a12f4",
  goal: "Restart the customer invoice sequence at INV/2026/10/0001",
  status: "pending",
  max_risk: "R4",
  environment: "production",
  expires_at: hoursFromNow(18),
  requester_id: "usr_tunde",
  approvals: [{ approver_id: "usr_kemi", user_id: "usr_kemi", decision: "approve" }],
  r3_blockers: ["distinct_approvers", "backup"],
  risk: {
    max: "R4",
    per_op: ["R4"],
    policy: { allow: true, approvers: 2, deny: false, needs_simulation: true, needs_backup: true, needs_window: true },
  },
  changes: [{ type: "sequence.update", description: "Set sequence account.sequence_out_invoice prefix INV/%(year)s/%(month)s/ and next number 1", params: { xmlid: "account.sequence_out_invoice", prefix: "INV/%(year)s/%(month)s/", number_next: 1 } }],
  assumptions: ["October has no posted customer invoices yet"],
  notChanging: ["data.delete", "module.uninstall", "rpc.write"],
  verify: ["postcondition:sequence.update"],
  undo: ["sequence.update inverse sequence.update"],
});

const APPROVED = card({
  plan_hash: "44ad0e9b1c7f2e80",
  schema_fp: "sfp_19be33a0",
  goal: "Add a Delivery window field to sales orders",
  status: "approved",
  max_risk: "R2",
  environment: "staging",
  expires_at: hoursFromNow(24 * 5),
  requester_id: "usr_tunde",
  approvals: [{ approver_id: "usr_amaka", user_id: "usr_amaka", decision: "approve" }],
  risk: { max: "R2", per_op: ["R2", "R1"], policy: { allow: true, approvers: 1, deny: false } },
  changes: [
    { type: "field.create", description: "Create field x_delivery_window (selection) on sale.order", params: { model: "sale.order", name: "x_delivery_window", ttype: "selection" } },
    { type: "view.inherit.create", description: "Show x_delivery_window after commitment_date on the sales order form", params: { model: "sale.order", anchor: "commitment_date" } },
  ],
  assumptions: ["Morning, afternoon, and evening are the only windows"],
  notChanging: ["data.delete", "module.uninstall", "rpc.write"],
  verify: ["postcondition:field.create", "postcondition:view.inherit.create"],
  undo: ["field.create inverse field.delete", "view.inherit.create inverse view.archive"],
});

const EXPIRED = card({
  plan_hash: "e3017c55d2a98b14",
  schema_fp: "sfp_5a6b7c8d",
  goal: "Turn on the overdue reminder automation for unpaid invoices",
  status: "pending",
  max_risk: "R2",
  environment: "production",
  expires_at: hoursFromNow(-3),
  requester_id: "usr_tunde",
  approvals: [],
  risk: { max: "R2", per_op: ["R2"], policy: { allow: true, approvers: 1, deny: false, needs_simulation: true } },
  changes: [{ type: "automation.update", description: "Enable automation Overdue invoice reminder", params: { name: "Overdue invoice reminder", active: true } }],
  assumptions: ["Reminder emails use the existing template"],
  notChanging: ["data.delete", "module.uninstall", "rpc.write"],
  verify: ["postcondition:automation.update"],
  undo: ["automation.update inverse automation.update"],
});

const VOIDED = card({
  plan_hash: "70c9b3e1f45a2d68",
  schema_fp: "sfp_0f1e2d3c",
  goal: "Rename the Sales menu to Orders",
  status: "voided",
  max_risk: "R1",
  environment: "staging",
  expires_at: hoursFromNow(24 * 4),
  requester_id: "usr_tunde",
  approvals: [],
  risk: { max: "R1", per_op: ["R1"], policy: { allow: true, approvers: 1, deny: false } },
  changes: [{ type: "menu.update", description: "Rename menu sale.sale_menu_root to Orders", params: { xmlid: "sale.sale_menu_root", name: "Orders" } }],
  assumptions: [],
  notChanging: ["data.delete", "module.uninstall", "rpc.write"],
  verify: ["postcondition:menu.update"],
  undo: ["menu.update inverse menu.update"],
});

const ALL = [R3, R4, R1, APPROVED, EXPIRED, VOIDED];

const STATES = [
  "idle",
  "loading",
  "empty",
  "error",
  "r1",
  "r3",
  "r3-confirm",
  "r4",
  "r4-self",
  "stale",
  "expired",
  "approved",
  "not-found",
  "signed-out",
  "forbidden",
] as const;
type HarnessState = (typeof STATES)[number];

const IDLE: PlanDecisionState = { busy: null, message: null, failure: null };

function setup(state: HarnessState): {
  phase: PlanInboxPhase;
  plans: InboxPlanCard[];
  selected: string | null;
  missing: string | null;
  viewer: string | null;
  stale: Set<string>;
  decision: PlanDecisionState;
  confirm: PlanDecision | null;
} {
  const base = {
    phase: "ready" as PlanInboxPhase,
    plans: ALL,
    selected: R3.plan_hash,
    missing: null as string | null,
    viewer: VIEWER as string | null,
    stale: new Set<string>(),
    decision: IDLE,
    confirm: null as PlanDecision | null,
  };
  switch (state) {
    case "idle":
      return { ...base, phase: "idle", plans: [], selected: null };
    case "loading":
      return { ...base, phase: "loading", plans: [], selected: null };
    case "empty":
      return { ...base, plans: [], selected: null };
    case "error":
      return { ...base, phase: "error", plans: [], selected: null };
    case "r1":
      return { ...base, selected: R1.plan_hash };
    case "r3-confirm":
      return { ...base, confirm: "approve" };
    case "r4":
      return { ...base, selected: R4.plan_hash };
    case "r4-self":
      return { ...base, selected: R4.plan_hash, viewer: "usr_kemi" };
    case "stale":
      return { ...base, stale: new Set([R3.plan_hash]), decision: { busy: null, message: null, failure: decideFailure(409, "plan_stale") } };
    case "expired":
      return { ...base, selected: EXPIRED.plan_hash };
    case "approved":
      return {
        ...base,
        selected: APPROVED.plan_hash,
        decision: { busy: null, message: "Approved. Not applied yet. The executor applies it after rechecking the fingerprint.", failure: null },
      };
    case "not-found":
      return { ...base, selected: null, missing: "deadbeef00112233" };
    case "signed-out":
      return { ...base, viewer: null };
    case "forbidden":
      return { ...base, decision: { busy: null, message: null, failure: decideFailure(403, "the requester cannot approve this risk") } };
    default:
      return base;
  }
}

function PlanInboxHarnessInner() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const searchParams = useSearchParams();
  const raw = searchParams.get("state") || "r3";
  const state = (STATES.includes(raw as HarnessState) ? raw : "r3") as HarnessState;
  const initial = setup(state);
  const [connectionId, setConnectionId] = useState(initial.phase === "idle" ? "" : CONNECTION);
  const [selected, setSelected] = useState<string | null>(initial.selected);

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  return (
    <div data-harness-state={state}>
      <PlanInboxView
        connectionId={connectionId}
        onConnectionChange={setConnectionId}
        onOpen={() => {}}
        onRefresh={() => {}}
        phase={initial.phase}
        plans={initial.plans}
        loadedConnectionId={CONNECTION}
        selectedHash={selected}
        missingHash={initial.missing}
        onSelect={setSelected}
        viewerId={initial.viewer}
        staleHashes={initial.stale}
        decision={initial.decision}
        onDecide={() => {}}
        now={NOW}
        timeZone="Africa/Lagos"
        initialConfirm={initial.confirm}
      />
    </div>
  );
}

export default function PlanInboxHarnessPage() {
  return (
    <Suspense fallback={null}>
      <PlanInboxHarnessInner />
    </Suspense>
  );
}
