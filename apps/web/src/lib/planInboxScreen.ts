/**
 * UI-S-50 Plan inbox (`/approvals`) screen logic and copy.
 * Pure helpers. No React.
 *
 * Honesty rules this file encodes:
 * - Approve records a sign-off on one plan fingerprint (plan hash + schema
 *   fingerprint). It never writes to Odoo. The executor applies an approved
 *   plan later and rechecks the fingerprint, freeze window, and expiry first.
 * - Approver slots come from the engine policy on the card, not from the UI.
 * - Section titles and bodies are engine strings and are rendered as sent.
 * - A missing or foreign plan reads "not found", never "forbidden".
 */

export const PAGE_TITLE = "Plan inbox";
export const PAGE_DESCRIPTION =
  "Read the plan, then sign the exact fingerprint. Odoo changes only when the executor applies it.";
export const SIGN_OFF_NOTE =
  "Approving records your signature on this fingerprint. Nothing is written to Odoo from this page.";
export const PRIMARY_CTA = "Approve this fingerprint";
export const CONFIRM_APPROVE_CTA = "Approve fingerprint";
export const CONFIRM_DENY_CTA = "Deny plan";
export const CONFIRM_STOP_CTA = "Deny and stop";
export const DENY_CTA = "Deny";
export const STOP_CTA = "Deny and stop the run";
export const OPEN_INBOX_CTA = "Open inbox";
export const REFRESH_CTA = "Refresh inbox";
export const CONNECTION_LABEL = "Connection";

export const PLAN_INBOX_STEPS = ["Engine plan", "Your approval", "Executor apply"] as const;
export type PlanInboxStepState = "done" | "current" | "todo" | "blocked";

export type PlanInboxGuide = { title: string; why: string; next: string };

export type PlanSection = { title: string; body: string };

export type PlanChange = {
  type?: string;
  description?: string;
  params?: Record<string, unknown>;
  billable_warning?: string;
};

export type PlanApproval = {
  approver_id?: string;
  user_id?: string;
  decision?: string;
  role?: string;
  domain_owner?: boolean;
};

export type PlanPolicy = {
  allow?: boolean;
  approvers?: number;
  deny?: boolean;
  needs_simulation?: boolean;
  domain_owner?: boolean;
  needs_backup?: boolean;
  needs_window?: boolean;
  expiry_hours?: number;
};

export type InboxPlanCard = {
  plan_hash: string;
  goal: string;
  status: string;
  max_risk: string;
  environment: string;
  expires_at: string;
  sections?: PlanSection[];
  changes?: PlanChange[];
  approvals?: PlanApproval[];
  risk?: { max?: string; per_op?: string[]; policy?: PlanPolicy };
  requester_id?: string;
  connection_id?: string;
  schema_fp?: string;
  r3_blockers?: string[];
};

export type PlanDecision = "approve" | "deny" | "deny_and_stop";

export type PlanDisplayStatus =
  | "pending"
  | "approved"
  | "denied"
  | "stopped"
  | "voided"
  | "stale"
  | "expired"
  | "blocked"
  | "unknown";

export type PlanStatusTone = "info" | "success" | "neutral" | "warning" | "danger";

export const PLAN_STATUS_META: Record<PlanDisplayStatus, { label: string; tone: PlanStatusTone }> = {
  pending: { label: "Waiting for approval", tone: "info" },
  approved: { label: "Approved, not applied", tone: "success" },
  denied: { label: "Denied", tone: "neutral" },
  stopped: { label: "Denied and stopped", tone: "neutral" },
  voided: { label: "Voided by a newer plan", tone: "neutral" },
  stale: { label: "Approval voided, fingerprint changed", tone: "warning" },
  expired: { label: "Expired", tone: "warning" },
  blocked: { label: "Denied by policy", tone: "danger" },
  unknown: { label: "Status unknown", tone: "neutral" },
};

/** Risk class meaning, from docs/plans/next-phase/02_APPROVAL_FLOW.md step 5. */
const RISK_MEANING: Record<string, string> = {
  R0: "Read only",
  R1: "Cosmetic and reversible",
  R2: "Functional configuration",
  R3: "Security, money, mass data, outbound, code, or modules",
  R4: "Heavy or prohibited",
};

const BLOCKER_COPY: Record<string, string> = {
  distinct_approvers: "A second, different person still has to approve.",
  domain_owner: "The domain owner for this protected target has not approved.",
  simulation: "No passing simulation is recorded on the card.",
  backup: "No backup id is recorded on the card.",
  window: "The clock is outside the allowed change window.",
};

/** Strip em and en dashes from UI copy (playbook law 9). */
export function sanitizePlanInboxCopy(text: string): string {
  return text.replace(/[\u2014\u2013]/g, "-");
}

export function riskMeaning(risk: string): string {
  return RISK_MEANING[risk] ?? "Unknown risk class";
}

export function environmentLabel(environment: string): string {
  const env = (environment || "").toLowerCase();
  if (env === "production") return "Production";
  if (env === "staging") return "Staging";
  return environment || "Unknown environment";
}

/** First 12 hex characters, enough to compare by eye. The full hash stays in the card. */
export function shortFingerprint(hash: string): string {
  return (hash || "").slice(0, 12);
}

function parseExpiry(raw: string): number | null {
  if (!raw || !raw.trim()) return null;
  const hasZone = /([zZ]|[+-]\d{2}:?\d{2})$/.test(raw.trim());
  const ms = Date.parse(hasZone ? raw : `${raw}Z`);
  return Number.isNaN(ms) ? null : ms;
}

/** Mirrors `approval_is_expired`: missing or unparseable counts as expired. */
export function isPlanExpired(plan: Pick<InboxPlanCard, "expires_at">, now: Date): boolean {
  const ms = parseExpiry(plan.expires_at);
  if (ms === null) return true;
  return now.getTime() >= ms;
}

export function planPolicy(plan: InboxPlanCard): PlanPolicy {
  const policy = plan.risk?.policy;
  return policy && typeof policy === "object" ? policy : {};
}

export function planDisplayStatus(
  plan: InboxPlanCard,
  now: Date,
  opts: { stale?: boolean } = {},
): PlanDisplayStatus {
  if (opts.stale) return "stale";
  const status = (plan.status || "").toLowerCase();
  if (status === "pending" || status === "approved") {
    if (isPlanExpired(plan, now)) return "expired";
  }
  if (status === "pending" && planPolicy(plan).deny) return "blocked";
  if (
    status === "pending" ||
    status === "approved" ||
    status === "denied" ||
    status === "stopped" ||
    status === "voided"
  ) {
    return status;
  }
  return "unknown";
}

export function isActionable(plan: InboxPlanCard, now: Date): boolean {
  return planDisplayStatus(plan, now) === "pending";
}

/** Actionable plans first; API order (newest first) kept inside each group. */
export function sortPlans(plans: InboxPlanCard[], now: Date): InboxPlanCard[] {
  const open = plans.filter((plan) => isActionable(plan, now));
  const rest = plans.filter((plan) => !isActionable(plan, now));
  return [...open, ...rest];
}

export function countActionable(plans: InboxPlanCard[], now: Date): number {
  return plans.filter((plan) => isActionable(plan, now)).length;
}

function personOf(approval: PlanApproval): string {
  return String(approval.user_id || approval.approver_id || "").trim();
}

export type ApproverSlot = { index: number; person: string | null };

/**
 * Approver slots from engine policy. Production heavy R4 asks for two distinct
 * people; R1 to R3 ask for one. A person who approved twice fills one slot.
 */
export function approverSlots(plan: InboxPlanCard): {
  needed: number;
  slots: ApproverSlot[];
  people: string[];
  distinctRequired: boolean;
} {
  const policy = planPolicy(plan);
  const raw = Number(policy.approvers);
  const needed = Number.isFinite(raw) && raw >= 0 ? Math.floor(raw) : 1;
  const people: string[] = [];
  for (const approval of plan.approvals ?? []) {
    if (approval.decision !== "approve") continue;
    const person = personOf(approval);
    if (person && !people.includes(person)) people.push(person);
  }
  const slotCount = Math.max(needed, people.length);
  const slots: ApproverSlot[] = Array.from({ length: slotCount }, (_, i) => ({
    index: i + 1,
    person: people[i] ?? null,
  }));
  return { needed, slots, people, distinctRequired: needed >= 2 };
}

export function blockerLines(plan: InboxPlanCard): string[] {
  return (plan.r3_blockers ?? [])
    .filter((item) => item !== "not_heavy_r4")
    .map((item) => BLOCKER_COPY[item] ?? sanitizePlanInboxCopy(item.replace(/_/g, " ")));
}

export type ApproveGate = { allowed: boolean; reason: PlanInboxGuide | null };

/** Whether this viewer can record an approval now. The server still decides. */
export function approveGate(
  plan: InboxPlanCard,
  now: Date,
  viewerId: string | null,
  opts: { stale?: boolean } = {},
): ApproveGate {
  const status = planDisplayStatus(plan, now, opts);
  if (status !== "pending") return { allowed: false, reason: statusGuide(plan, status, now) };
  if (!plan.schema_fp) {
    return {
      allowed: false,
      reason: {
        title: "This card has no schema fingerprint",
        why: "An approval binds to the plan hash and the schema fingerprint together. Without the second one, the approval could not be checked at apply time.",
        next: "Ask the requester to submit the plan again so the engine binds a fresh fingerprint.",
      },
    };
  }
  if (!viewerId) {
    return {
      allowed: false,
      reason: {
        title: "Sign in to approve",
        why: "Your account id is the approver on the record. Without a session the inbox can show the card but cannot record a sign-off.",
        next: "Sign in, then reopen this inbox.",
      },
    };
  }
  const { distinctRequired, people } = approverSlots(plan);
  if (distinctRequired && people.includes(viewerId)) {
    return {
      allowed: false,
      reason: {
        title: "You already approved this fingerprint",
        why: "This plan needs two different people. One person cannot fill both slots, including through a second login.",
        next: "Ask a second approver to open this inbox and approve the same fingerprint.",
      },
    };
  }
  return { allowed: true, reason: null };
}

export function stepStates(status: PlanDisplayStatus): PlanInboxStepState[] {
  switch (status) {
    case "pending":
      return ["done", "current", "todo"];
    case "approved":
      return ["done", "done", "current"];
    case "unknown":
      return ["done", "todo", "todo"];
    default:
      return ["done", "blocked", "todo"];
  }
}

const RTF_UNITS: { unit: Intl.RelativeTimeFormatUnit; ms: number }[] = [
  { unit: "day", ms: 86_400_000 },
  { unit: "hour", ms: 3_600_000 },
  { unit: "minute", ms: 60_000 },
];

/** "Expires in 23 hours" / "Expired 2 hours ago". */
export function expiryPhrase(plan: Pick<InboxPlanCard, "expires_at">, now: Date): string {
  const ms = parseExpiry(plan.expires_at);
  if (ms === null) return "No valid expiry on the card";
  const delta = ms - now.getTime();
  const abs = Math.abs(delta);
  const pick = RTF_UNITS.find((u) => abs >= u.ms) ?? RTF_UNITS[RTF_UNITS.length - 1];
  const value = Math.max(1, Math.round(abs / pick.ms));
  const unit = value === 1 ? pick.unit : `${pick.unit}s`;
  return delta > 0 ? `Expires in ${value} ${unit}` : `Expired ${value} ${unit} ago`;
}

export function expiryAbsolute(
  plan: Pick<InboxPlanCard, "expires_at">,
  opts: { timeZone?: string; locale?: string } = {},
): string {
  const ms = parseExpiry(plan.expires_at);
  if (ms === null) return "";
  return new Intl.DateTimeFormat(opts.locale ?? "en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone: opts.timeZone,
    timeZoneName: "short",
  }).format(new Date(ms));
}

export type TimelineStep = { label: string; detail: string; state: PlanInboxStepState };

/** Engine plan, your approval, executor apply, with one honest line each. */
export function timelineSteps(plan: InboxPlanCard, status: PlanDisplayStatus): TimelineStep[] {
  const states = stepStates(status);
  const { needed, people } = approverSlots(plan);
  const approvalDetail: Record<PlanDisplayStatus, string> = {
    pending:
      needed <= 1
        ? `${people.length} of 1 signature`
        : `${people.length} of ${needed} signatures, from different people`,
    approved: "Signed. Every required approval is on the card.",
    denied: "Denied. This fingerprint is closed.",
    stopped: "Denied and the run stopped.",
    voided: "Moved to a newer plan with the same changes.",
    stale: "Fingerprint changed. Your signature was not kept.",
    expired: "The approval window closed.",
    blocked: "Policy denies this class for every approver.",
    unknown: "The engine sent a status this page does not know.",
  };
  return [
    {
      label: PLAN_INBOX_STEPS[0],
      detail: "Rendered from the change-set by the engine. The model does not write the card.",
      state: states[0],
    },
    { label: PLAN_INBOX_STEPS[1], detail: approvalDetail[status], state: states[1] },
    {
      label: PLAN_INBOX_STEPS[2],
      detail:
        status === "approved"
          ? "Next. Rechecks fingerprint, freeze window, and expiry before any write."
          : "Runs only after approval, never from this page.",
      state: states[2],
    },
  ];
}

/** Amber caution only where the risk is real: R3 and R4 cards that are still open. */
export function riskCaution(plan: InboxPlanCard, status: PlanDisplayStatus): PlanInboxGuide | null {
  if (status !== "pending") return null;
  const env = environmentLabel(plan.environment).toLowerCase();
  if (plan.max_risk === "R3") {
    return {
      title: `R3 on ${env}`,
      why: "Security, money, mass data, outbound messages, code, or modules.",
      next: "Read each change and the risk section before you sign.",
    };
  }
  if (plan.max_risk === "R4") {
    const heavyProd = (planPolicy(plan).approvers ?? 0) >= 2;
    return {
      title: heavyProd ? "Heavy R4 on production" : `Heavy R4 on ${env}`,
      why: heavyProd
        ? "Two different people, a passing simulation, a backup, and an open change window are all required."
        : "One approval on staging. Production would need two people and recorded evidence.",
      next: "Check the blockers below. Signing does not clear them for you.",
    };
  }
  return null;
}

export function noConnectionGuide(): PlanInboxGuide {
  return {
    title: "Pick a connection to see its plans",
    why: "Plans are scoped to one connection. A card for another client is never listed here.",
    next: "Enter the connection id, or open this inbox from Command center.",
  };
}

export function emptyInboxGuide(connectionId: string): PlanInboxGuide {
  return {
    title: "No plans for this connection",
    why: `The engine has not submitted a gated change for ${connectionId || "this connection"} yet, or it is not one you can see.`,
    next: "Run a change that needs approval from a build screen, then refresh this inbox.",
  };
}

export function loadErrorGuide(): PlanInboxGuide {
  return {
    title: "The inbox could not be loaded",
    why: "The request to the plan inbox failed before any plans came back. Nothing was approved or changed.",
    next: "Check the connection id and your network, then refresh the inbox.",
  };
}

export function notFoundGuide(hash: string): PlanInboxGuide {
  return {
    title: "Plan not found",
    why: `No plan with fingerprint ${shortFingerprint(hash) || "that id"} is on this connection. It may belong to another connection or have been removed.`,
    next: "Pick a plan from the list, or open the link again from the connection that sent it.",
  };
}

export function staleGuide(): PlanInboxGuide {
  return {
    title: "Approval voided, the fingerprint changed",
    why: "The plan hash or schema fingerprint no longer matches what you were looking at. Your approval was not recorded.",
    next: "Refresh the inbox and review the current card before approving again.",
  };
}

export function statusGuide(
  plan: InboxPlanCard,
  status: PlanDisplayStatus,
  now: Date,
): PlanInboxGuide | null {
  switch (status) {
    case "pending":
      return null;
    case "approved":
      return {
        title: "Approved. Not applied yet.",
        why: "Every required approval is recorded on this fingerprint. Nothing has been written to Odoo by approving.",
        next: `The executor applies it next and rechecks the fingerprint first. ${expiryPhrase(plan, now)}.`,
      };
    case "denied":
      return {
        title: "This plan was denied",
        why: "An approver denied this fingerprint. It cannot be applied.",
        next: "Ask the requester to revise the change and submit a new plan.",
      };
    case "stopped":
      return {
        title: "Denied and the run was stopped",
        why: "An approver denied this fingerprint and stopped the run that produced it.",
        next: "Start a new run when the change is ready to plan again.",
      };
    case "voided":
      return {
        title: "Voided by a newer plan",
        why: "The engine submitted a newer plan with the same changes, so approval moved to that card.",
        next: "Open the newest waiting plan in this list.",
      };
    case "stale":
      return staleGuide();
    case "expired":
      return {
        title: "This plan expired",
        why: `The approval window closed. ${expiryPhrase(plan, now)}. An expired plan cannot be approved or applied.`,
        next: "Ask the requester to submit the plan again for a fresh window.",
      };
    case "blocked":
      return {
        title: "Denied by policy",
        why: "This change is a hard-stop R4 class. Policy denies it for every approver.",
        next: "Change the plan so it avoids the prohibited operation, then submit it again.",
      };
    default:
      return {
        title: "Status unknown",
        why: `The engine sent status "${sanitizePlanInboxCopy(plan.status || "empty")}", which this inbox does not recognise.`,
        next: "Refresh the inbox. If it stays, report the plan fingerprint.",
      };
  }
}

export type DecideFailure = { kind: "stale" | "frozen" | "not_found" | "forbidden" | "invalid" | "network" | "server"; guide: PlanInboxGuide };

/** Map a failed decide call to what/why/next. 404 always reads "not found". */
export function decideFailure(status: number | null, detailError?: string): DecideFailure {
  if (status === null) {
    return {
      kind: "network",
      guide: {
        title: "The decision did not reach the server",
        why: "The network request failed. Nothing was recorded on this plan.",
        next: "Check your connection and try again.",
      },
    };
  }
  if (status === 409 && detailError === "frozen") {
    return {
      kind: "frozen",
      guide: {
        title: "A freeze window is on",
        why: "Approvals are paused for this connection while the freeze lasts. Nothing was recorded.",
        next: "Approve after the freeze ends, or ask the owner to lift it.",
      },
    };
  }
  if (status === 409) {
    return { kind: "stale", guide: staleGuide() };
  }
  if (status === 404) {
    return { kind: "not_found", guide: notFoundGuide("") };
  }
  if (status === 403) {
    const requester = (detailError || "").includes("requester");
    return {
      kind: "forbidden",
      guide: requester
        ? {
            title: "The requester cannot approve this risk",
            why: "Policy keeps the person who asked for this change out of the approver slot at this risk class.",
            next: "Ask a different approver to open this inbox and approve the fingerprint.",
          }
        : {
            title: "Your role cannot decide on plans",
            why: "This account can read the inbox for this connection but cannot record approvals.",
            next: "Ask the workspace owner for an approver grant on this connection.",
          },
    };
  }
  if (status === 422) {
    return {
      kind: "invalid",
      guide: {
        title: "The decision was rejected as incomplete",
        why: "The server could not read the plan hash, schema fingerprint, or decision in the request.",
        next: "Refresh the inbox and try again from the current card.",
      },
    };
  }
  return {
    kind: "server",
    guide: {
      title: "The decision could not be recorded",
      why: `The server answered ${status}. Nothing was recorded on this plan.`,
      next: "Try again in a moment. If it keeps failing, report the plan fingerprint.",
    },
  };
}

export function decisionRecordedMessage(card: InboxPlanCard, decision: PlanDecision, now: Date): string {
  if (decision === "deny") return "Plan denied. It cannot be applied.";
  if (decision === "deny_and_stop") return "Plan denied and the run stopped.";
  const status = planDisplayStatus(card, now);
  if (status === "approved") return "Approved. Not applied yet. The executor applies it after rechecking the fingerprint.";
  const { needed, people } = approverSlots(card);
  return `Approval recorded. ${people.length} of ${needed} approvals.`;
}

export function confirmCopy(plan: InboxPlanCard, decision: PlanDecision, now: Date): { title: string; body: string; cta: string } {
  const fp = shortFingerprint(plan.plan_hash);
  const env = environmentLabel(plan.environment).toLowerCase();
  if (decision === "approve") {
    return {
      title: `Approve ${fp} for ${env}?`,
      body: `This records your sign-off on this exact fingerprint. Odoo does not change now. ${expiryPhrase(plan, now)}.`,
      cta: CONFIRM_APPROVE_CTA,
    };
  }
  if (decision === "deny") {
    return {
      title: `Deny ${fp}?`,
      body: "The plan is closed and cannot be applied. The requester can submit a revised plan.",
      cta: CONFIRM_DENY_CTA,
    };
  }
  return {
    title: `Deny ${fp} and stop the run?`,
    body: "The plan is closed and the run that produced it stops. A new run starts from planning again.",
    cta: CONFIRM_STOP_CTA,
  };
}
