/**
 * UI-S-52 Bots / Bridge pass: Contract Studio (`/bridge/contracts/new`) screen logic.
 * Pure helpers and copy. No React.
 *
 * Honesty for connect / send: Tier I only reads the contract and the two
 * connection records. It opens no session, sends no webhook, and writes
 * nothing to Odoo. One teal primary: Validate tier I.
 */

export const PAGE_TITLE = "Contract Studio";
export const PAGE_LEAD =
  "Describe how orders move between one Odoo connection and one third-party connection. Tier I checks the contract before anything can sync.";
export const PRIMARY_CTA = "Validate tier I";
export const PRIMARY_CTA_BUSY = "Validating…";
export const RESET_CTA = "Clear form";
export const ENTITY_NAME = "orders";
export const IDEMPOTENCY_FIELD = "idempotency_key";

export type Direction = "inbound" | "outbound" | "two_way";
export type Policy = "odoo_wins" | "remote_wins" | "manual";

export type ContractForm = {
  odooId: string;
  thirdId: string;
  direction: Direction;
  conflict: Policy | "";
  money: boolean;
  moneyPolicy: Policy;
};

export const EMPTY_FORM: ContractForm = {
  odooId: "",
  thirdId: "",
  direction: "inbound",
  conflict: "",
  money: true,
  moneyPolicy: "odoo_wins",
};

export const DIRECTION_OPTIONS: { value: Direction; label: string; hint: string }[] = [
  { value: "inbound", label: "Inbound", hint: "Third-party into Odoo" },
  { value: "outbound", label: "Outbound", hint: "Odoo out to the third party" },
  { value: "two_way", label: "Two-way", hint: "Both ways. Needs a conflict rule" },
];

export const POLICY_OPTIONS: { value: Policy; label: string; hint: string }[] = [
  { value: "odoo_wins", label: "Odoo wins", hint: "Odoo keeps its value" },
  { value: "remote_wins", label: "Remote wins", hint: "The third party overwrites Odoo" },
  { value: "manual", label: "Manual", hint: "Hold the record for a person to decide" },
];

export function directionLabel(direction: string | undefined): string {
  const hit = DIRECTION_OPTIONS.find((o) => o.value === direction);
  return hit ? hit.label.toLowerCase() : String(direction ?? "this direction");
}

export type StepId = "connections" | "direction" | "money" | "validate";
export const STEPS: { id: StepId; label: string }[] = [
  { id: "connections", label: "Connections" },
  { id: "direction", label: "Direction" },
  { id: "money", label: "Money" },
  { id: "validate", label: "Validate" },
];

export type StepState = "done" | "current" | "todo" | "blocked";

/** Rail state is derived from the form, never typed by hand. Linear: first incomplete step is current. */
export function stepStates(
  form: ContractForm,
  passed: boolean,
  blocked: StepId | null = null,
): Record<StepId, StepState> {
  const odoo = form.odooId.trim();
  const third = form.thirdId.trim();
  const connections = odoo !== "" && third !== "" && odoo !== third;
  const direction = form.direction !== "two_way" || form.conflict !== "";
  const done: Record<StepId, boolean> = {
    connections,
    direction,
    // Money never blocks; it reads as done once the steps before it are.
    money: connections && direction,
    validate: passed,
  };
  const out = {} as Record<StepId, StepState>;
  let reachedCurrent = false;
  for (const step of STEPS) {
    if (reachedCurrent) {
      out[step.id] = "todo";
    } else if (blocked === step.id) {
      // Tier I refused because of this step: never show it as done.
      out[step.id] = "blocked";
      reachedCurrent = true;
    } else if (done[step.id]) {
      out[step.id] = "done";
    } else {
      out[step.id] = "current";
      reachedCurrent = true;
    }
  }
  return out;
}

export type FieldKey = "odooId" | "thirdId" | "conflict" | "moneyPolicy";
export type FieldErrors = Partial<Record<FieldKey, string>>;

/** Client-side Tier I mirror. Errors are instructions, written per field. */
export function validateForm(form: ContractForm): FieldErrors {
  const errors: FieldErrors = {};
  const odoo = form.odooId.trim();
  const third = form.thirdId.trim();
  if (!odoo) errors.odooId = "Enter the Odoo connection id.";
  if (!third) errors.thirdId = "Enter the third-party connection id.";
  if (odoo && third && odoo === third) {
    errors.thirdId = "Use a different connection from the Odoo one.";
  }
  if (form.direction === "two_way" && !form.conflict) {
    errors.conflict = "Choose who wins when both sides change the same order.";
  }
  if (form.money && !form.moneyPolicy) {
    errors.moneyPolicy = "Choose a money policy for orders.";
  }
  return errors;
}

export const FIELD_ORDER: FieldKey[] = ["odooId", "thirdId", "conflict", "moneyPolicy"];

export function firstErrorField(errors: FieldErrors): FieldKey | null {
  return FIELD_ORDER.find((key) => errors[key]) ?? null;
}

/** Exact body POSTed to /api/bridge/contracts/validate. No secrets, ids only. */
export function buildContract(form: ContractForm): Record<string, unknown> {
  const contract: Record<string, unknown> = {
    odoo_connection_id: form.odooId.trim(),
    third_party_connection_id: form.thirdId.trim(),
    direction: form.direction,
    webhook_signature_required: true,
    entities: [
      {
        name: ENTITY_NAME,
        money: form.money,
        money_policy: form.money ? form.moneyPolicy : null,
      },
    ],
  };
  if (form.direction === "two_way") {
    contract.conflict_resolution = form.conflict || null;
  }
  return contract;
}

export type TierResult = {
  ok: boolean;
  tier: string;
  error?: string;
  direction?: string;
  entities?: number;
};

export type Guide = { title: string; why: string; next: string };
export type Side = "odoo" | "third_party";

export type Outcome =
  | { kind: "passed"; result: TierResult; guide: Guide }
  | {
      kind: "refused";
      result: TierResult;
      guide: Guide;
      /** Rail step Tier I blamed, shown as blocked until the user edits. */
      step: StepId;
      /** Per-side connection status when Tier I reached the verify gate. */
      sides?: Partial<Record<Side, string>>;
      field?: FieldKey;
      fieldMessage?: string;
    }
  | { kind: "error"; guide: Guide };

/** Strip em / en dashes from UI copy (playbook law 9). */
export function sanitizeCopy(text: string): string {
  return text.replace(/[\u2014\u2013]/g, "-");
}

export function honestyGuide(): Guide {
  return {
    title: "Validating does not connect or send anything",
    why: "Tier I reads this contract and the two connection records. It opens no session, sends no webhook, and writes nothing to Odoo.",
    next: "Verify both connections first. Secrets stay on the connection and never belong in this contract.",
  };
}

function describeRefusedConnection(entry: string): string {
  // Backend shape: "odoo:abc (missing)" or "third_party:shop-1 (failed)".
  const match = entry.trim().match(/^(odoo|third_party):(.+?)\s*\(([^)]*)\)$/);
  if (!match) return entry.trim();
  const [, side, id, status] = match;
  const who = side === "odoo" ? "Odoo connection" : "Third-party connection";
  const state =
    status === "missing" ? "was not found" : status ? `is ${status.replace(/_/g, " ")}` : "is not verified";
  return `${who} ${id.trim()} ${state}`;
}

/** Map a Tier I response to a what / why / next outcome. */
export function classifyResult(result: TierResult): Outcome {
  if (result.ok) {
    const n = typeof result.entities === "number" ? result.entities : 1;
    return {
      kind: "passed",
      result,
      guide: {
        title: `Tier ${result.tier || "I"} passed for ${directionLabel(result.direction)}`,
        why: `The contract is complete, carries no secrets, and both connections are verified. ${n} ${n === 1 ? "entity" : "entities"} checked.`,
        next: "Nothing has synced. Keep these settings for sync setup; this screen does not save or start a sync.",
      },
    };
  }
  const raw = sanitizeCopy(String(result.error ?? "").trim());
  const lower = raw.toLowerCase();

  if (lower.includes("requires verified connections")) {
    const list = raw.split(":").slice(1).join(":");
    const chunks = list.split(/,(?=\s*(?:odoo|third_party):)/);
    const parts = chunks.map((p) => describeRefusedConnection(p)).filter(Boolean);
    const sides: Partial<Record<Side, string>> = {};
    for (const chunk of chunks) {
      const m = chunk.trim().match(/^(odoo|third_party):.+?\(([^)]*)\)$/);
      if (m) sides[m[1] as Side] = m[2] || "unverified";
    }
    return {
      kind: "refused",
      step: "connections",
      sides,
      result,
      guide: {
        title: "Connections are not verified",
        why: parts.length ? `${parts.join(". ")}.` : "One or both connections have no successful Verify on record.",
        next: "Run Verify on each connection until it succeeds, then validate again. Your entries are kept.",
      },
    };
  }
  if (lower.includes("must differ")) {
    return {
      kind: "refused",
      step: "connections",
      result,
      field: "thirdId",
      fieldMessage: "Use a different connection from the Odoo one.",
      guide: {
        title: "Both sides point at the same connection",
        why: "A contract links two different systems, so the ids cannot match.",
        next: "Pick the third-party connection id, then validate again.",
      },
    };
  }
  if (lower.includes("conflict_resolution")) {
    return {
      kind: "refused",
      step: "direction",
      result,
      field: "conflict",
      fieldMessage: "Choose who wins when both sides change the same order.",
      guide: {
        title: "Two-way needs a conflict rule",
        why: "When both systems edit the same order, Tier I refuses to guess which one wins.",
        next: "Choose a conflict rule under Direction, then validate again.",
      },
    };
  }
  if (lower.includes("money_policy")) {
    return {
      kind: "refused",
      step: "money",
      result,
      field: "moneyPolicy",
      fieldMessage: "Choose a money policy for orders.",
      guide: {
        title: "Orders carry money without a policy",
        why: "Amounts that disagree between systems need a rule before anything moves.",
        next: "Choose a money policy, then validate again.",
      },
    };
  }
  if (lower.includes("secret") || lower.includes("credentials")) {
    return {
      kind: "refused",
      step: "validate",
      result,
      guide: {
        title: "The contract carries a secret",
        why: raw || "A password, token, or key was found in the contract body.",
        next: "Move the secret onto its connection and reference the connection id here.",
      },
    };
  }
  return {
    kind: "refused",
    step: "validate",
    result,
    guide: {
      title: "Tier I refused the contract",
      why: raw || "The check returned no reason.",
      next: "Fix the field it names, then validate again. Nothing was sent or written.",
    },
  };
}

export function networkErrorGuide(status?: number): Guide {
  const why =
    typeof status === "number"
      ? `The request failed before a Tier I result came back (HTTP ${status}).`
      : "The request failed before a Tier I result came back.";
  return {
    title: "Could not reach Tier I",
    why,
    next: "Check that the Ingenium API is running, then validate again. Your entries are kept and nothing was sent.",
  };
}

/** Stable JSON preview of the exact request body. */
export function previewJson(form: ContractForm): string {
  return JSON.stringify({ contract: buildContract(form) }, null, 2);
}

export function formsEqual(a: ContractForm, b: ContractForm): boolean {
  return (
    a.odooId === b.odooId &&
    a.thirdId === b.thirdId &&
    a.direction === b.direction &&
    a.conflict === b.conflict &&
    a.money === b.money &&
    a.moneyPolicy === b.moneyPolicy
  );
}

/* ------------------------------------------------------------------
   Tier I ledger: the checks Tier I runs, as rows on the contract sheet.
   Local rows evaluate as the user types; connection rows need the server.
   ------------------------------------------------------------------ */

export type CheckId =
  | "distinct"
  | "conflict"
  | "money"
  | "signature"
  | "secrets"
  | "odoo_verified"
  | "third_verified";

/** pass / fail / na (not applicable) / wait (needs Tier I) / skip (Tier I stopped earlier). */
export type CheckStatus = "pass" | "fail" | "na" | "wait" | "skip";

export type CheckRow = { id: CheckId; label: string; status: CheckStatus; detail: string; source: "local" | "tier" };

function policyLabel(value: string): string {
  return POLICY_OPTIONS.find((o) => o.value === value)?.label ?? value;
}

function sideStatusDetail(status: string): string {
  if (status === "missing") return "Not found";
  return status ? status.charAt(0).toUpperCase() + status.slice(1).replace(/_/g, " ") : "Not verified";
}

export function buildLedger(
  form: ContractForm,
  outcome: Outcome | null,
  opts: { stale: boolean; pending: boolean },
): CheckRow[] {
  const odoo = form.odooId.trim();
  const third = form.thirdId.trim();
  const fresh = outcome && !opts.stale && !opts.pending ? outcome : null;

  const distinct: CheckRow = {
    id: "distinct",
    label: "Two different connections",
    source: "local",
    ...(!odoo || !third
      ? { status: "wait" as const, detail: "Needs both ids" }
      : odoo === third
        ? { status: "fail" as const, detail: "Both sides use the same id" }
        : { status: "pass" as const, detail: "Ids differ" }),
  };
  const conflict: CheckRow = {
    id: "conflict",
    label: "Conflict rule for two-way",
    source: "local",
    ...(form.direction !== "two_way"
      ? { status: "na" as const, detail: `Not needed for ${directionLabel(form.direction)}` }
      : form.conflict
        ? { status: "pass" as const, detail: policyLabel(form.conflict) }
        : { status: "fail" as const, detail: "Choose a rule" }),
  };
  const money: CheckRow = {
    id: "money",
    label: "Money policy on orders",
    source: "local",
    ...(!form.money
      ? { status: "na" as const, detail: "Orders carry no money" }
      : form.moneyPolicy
        ? { status: "pass" as const, detail: policyLabel(form.moneyPolicy) }
        : { status: "fail" as const, detail: "Choose a policy" }),
  };
  const signature: CheckRow = {
    id: "signature",
    label: "Webhook signature required",
    source: "local",
    status: "pass",
    detail: "Locked on",
  };
  const secretRefused =
    fresh?.kind === "refused" && /secret|credentials/i.test(String(fresh.result.error ?? ""));
  const secrets: CheckRow = {
    id: "secrets",
    label: "No secrets in the contract",
    source: "local",
    status: secretRefused ? "fail" : "pass",
    detail: secretRefused ? "Tier I found one" : "Ids only",
  };

  function sideRow(id: CheckId, side: Side, label: string, hasId: boolean): CheckRow {
    const base = { id, label, source: "tier" as const };
    if (opts.pending && hasId) return { ...base, status: "wait", detail: "Checking…" };
    if (!fresh) return { ...base, status: "wait", detail: opts.stale ? "Validate again" : "Checked on validate" };
    if (fresh.kind === "passed") return { ...base, status: "pass", detail: "Verified" };
    if (fresh.kind === "error") return { ...base, status: "skip", detail: "Not reached" };
    if (fresh.sides) {
      const st = fresh.sides[side];
      return st ? { ...base, status: "fail", detail: sideStatusDetail(st) } : { ...base, status: "pass", detail: "Verified" };
    }
    return { ...base, status: "skip", detail: "Not reached" };
  }

  return [
    distinct,
    conflict,
    money,
    signature,
    secrets,
    sideRow("odoo_verified", "odoo", "Odoo connection verified", Boolean(odoo)),
    sideRow("third_verified", "third_party", "Third-party connection verified", Boolean(third)),
  ];
}

export function ledgerSummary(rows: CheckRow[]): { passed: number; applicable: number; failed: number } {
  const applicable = rows.filter((r) => r.status !== "na");
  return {
    passed: applicable.filter((r) => r.status === "pass").length,
    applicable: applicable.length,
    failed: applicable.filter((r) => r.status === "fail").length,
  };
}

export type StatusChip = { label: string; tone: "neutral" | "success" | "danger" | "caution" };

export function statusChip(outcome: Outcome | null, opts: { stale: boolean; pending: boolean }): StatusChip {
  if (opts.pending) return { label: "Checking", tone: "neutral" };
  if (!outcome) return { label: "Draft", tone: "neutral" };
  if (opts.stale) return { label: "Edited since check", tone: "caution" };
  if (outcome.kind === "passed") return { label: "Tier I passed", tone: "success" };
  if (outcome.kind === "refused") return { label: "Refused", tone: "danger" };
  return { label: "Unreachable", tone: "danger" };
}

/** Real overwrite risk only. Returns null when nothing can overwrite Odoo. */
export function overwriteRisk(form: ContractForm): string | null {
  const money = form.money && form.moneyPolicy === "remote_wins";
  const conflict = form.direction === "two_way" && form.conflict === "remote_wins";
  if (money && conflict) {
    return "Remote wins on money and conflicts: the third party can overwrite Odoo order totals and edits once a sync runs.";
  }
  if (money) return "Remote wins on money: the third party can overwrite Odoo order totals once a sync runs.";
  if (conflict) return "Remote wins on conflicts: third-party edits replace Odoo edits to the same order once a sync runs.";
  return null;
}

export const HONESTY_LINE = "Read-only check. Nothing connects, sends, or syncs.";
