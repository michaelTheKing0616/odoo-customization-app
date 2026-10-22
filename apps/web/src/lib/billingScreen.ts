/**
 * UI-S-42 Billing (/settings/billing) screen logic and copy.
 * Pure helpers. No React. Prices come from the billing catalog (GET /api/billing/plans),
 * plan state from GET /api/billing/entitlements. Nothing here invents a number:
 * when the catalog is missing, money reads as unavailable rather than guessed.
 */

import type { BillingPlanRow, BillingPlansCatalog, EntitlementsOut } from "@/lib/api";

export const PAGE_TITLE = "Billing";
export const PAGE_DESCRIPTION =
  "Your plan, what Stripe will charge next, and what changes if you switch. Plan changes, payment method, and invoices open in Stripe.";
export const PRIMARY_CTA = "Manage plan";
export const BILLING_CTA = "Manage billing";
export const ADD_SLOT_CTA = "Add project slot";
export const ESTIMATE_NOTE =
  "Estimate from Ingenium list prices. Your Stripe invoice is final and includes tax, proration, and discounts.";

export type BillingGuide = { title: string; why: string; next: string };
export type Tone = "neutral" | "success" | "warning" | "danger";

/** Strip em / en dashes from UI copy (playbook section 0 law 9). */
export function sanitizeBillingCopy(text: string): string {
  return text.replace(/\s*[—–]\s*/g, ". ").replace(/\.\s*\./g, ".");
}

const USD = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const USD_WHOLE = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

export function formatUsd(amount: number | null | undefined, opts: { whole?: boolean } = {}): string {
  if (amount == null || !Number.isFinite(amount)) return "Unavailable";
  if (opts.whole && Number.isInteger(amount)) return USD_WHOLE.format(amount);
  return USD.format(amount);
}

const DATE = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });

export function formatBillingDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return null;
  return DATE.format(new Date(t));
}

export function daysUntil(iso: string | null | undefined, now: number = Date.now()): number | null {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return null;
  return Math.ceil((t - now) / 86_400_000);
}

export function relativeDays(days: number | null): string | null {
  if (days == null) return null;
  if (days < 0) return `${Math.abs(days)} day${Math.abs(days) === 1 ? "" : "s"} ago`;
  if (days === 0) return "today";
  if (days === 1) return "tomorrow";
  return `in ${days} days`;
}

export type StatusMeta = { label: string; tone: Tone; hint: string };

export function statusMeta(status: string | null | undefined): StatusMeta {
  switch ((status || "").toLowerCase()) {
    case "active":
      return { label: "Active", tone: "success", hint: "Stripe reports the subscription in good standing." };
    case "trialing":
      return { label: "Trial", tone: "neutral", hint: "Build features are unlocked until the trial ends." };
    case "past_due":
      return { label: "Payment failed", tone: "danger", hint: "Stripe could not collect the last invoice." };
    case "unpaid":
      return { label: "Unpaid", tone: "danger", hint: "Stripe stopped retrying the last invoice." };
    case "canceled":
      return { label: "Canceled", tone: "neutral", hint: "The subscription will not renew." };
    case "incomplete":
      return { label: "Checkout not finished", tone: "warning", hint: "The first payment did not complete." };
    case "expired":
      return { label: "Expired", tone: "neutral", hint: "The plan period has ended." };
    default:
      return { label: status ? status.replace(/_/g, " ") : "Unknown", tone: "neutral", hint: "Status as reported by the billing API." };
  }
}

export function findPlan(catalog: BillingPlansCatalog | null | undefined, planId: string | null | undefined): BillingPlanRow | null {
  if (!catalog || !planId) return null;
  return catalog.plans.find((p) => p.id === planId) ?? null;
}

const PLAN_NAMES: Record<string, string> = {
  free_solo: "Free Solo",
  pro: "Pro",
  business: "Business",
  agency: "Agency",
  internal: "Internal",
  project_pass: "Project Pass",
};

export function planDisplayName(planId: string, catalog?: BillingPlansCatalog | null): string {
  return findPlan(catalog, planId)?.display_name ?? PLAN_NAMES[planId] ?? planId.replace(/_/g, " ");
}

export function isInternalPlan(planId: string | null | undefined): boolean {
  return planId === "internal";
}

/** Free Solo, or any catalog plan whose list price is zero. Internal is handled on its own. */
export function isFreePlan(planId: string | null | undefined, catalog?: BillingPlansCatalog | null): boolean {
  if (!planId || isInternalPlan(planId)) return false;
  if (planId === "free_solo") return true;
  return findPlan(catalog, planId)?.monthly_usd === 0;
}

export function nextTier(catalog: BillingPlansCatalog | null | undefined, planId: string | null | undefined): BillingPlanRow | null {
  if (!catalog || !planId) return null;
  const order = catalog.tier_order;
  const idx = order.indexOf(planId);
  if (idx < 0 || idx >= order.length - 1) return null;
  return findPlan(catalog, order[idx + 1]);
}

export type PrimaryAction =
  | { kind: "portal"; label: string; hint: string }
  | { kind: "picker"; label: string; hint: string }
  | { kind: "none"; label: string; hint: string };

/**
 * One teal primary on the screen: Manage plan.
 * Paid plans manage in the Stripe portal. Free Solo and in-app trials have no Stripe subscription
 * to manage, so Manage plan opens the in-sheet plan chooser (checkout on Stripe).
 * Internal is not billed, so it is disabled with a reason.
 */
export function primaryAction(
  planId: string | null | undefined,
  status?: string | null,
  catalog?: BillingPlansCatalog | null,
): PrimaryAction {
  if (isInternalPlan(planId)) {
    return {
      kind: "none",
      label: PRIMARY_CTA,
      hint: "Internal workspaces have no Stripe subscription, so there is no plan to change here.",
    };
  }
  const s = (status || "").toLowerCase();
  if (isFreePlan(planId, catalog) || s === "trialing" || s === "canceled" || s === "expired") {
    return {
      kind: "picker",
      label: PRIMARY_CTA,
      hint: "Opens the tier chooser on this sheet. Checkout runs on Stripe, and nothing is charged until you confirm there.",
    };
  }
  return {
    kind: "portal",
    label: PRIMARY_CTA,
    hint: "Opens the Stripe customer portal to switch tier or cancel. Changes apply when Stripe confirms them.",
  };
}

export type ChooserTier = {
  id: string;
  name: string;
  price: number | null;
  slotPrice: number | null;
  cta: string;
  delta: string;
  current: boolean;
};

/** Paid tiers a free, trial, or canceled workspace can check out, with honest gain or loss counts. */
export function chooserTiers(
  catalog: BillingPlansCatalog | null | undefined,
  planId: string | null | undefined,
  features: Record<string, string>,
  status?: string | null,
): ChooserTier[] {
  if (!catalog) return [];
  const trialing = (status || "").toLowerCase() === "trialing";
  return catalog.tier_order
    .map((id) => findPlan(catalog, id))
    .filter((p): p is BillingPlanRow => Boolean(p) && (p as BillingPlanRow).monthly_usd !== 0)
    .map((p) => {
      let gains = 0;
      let losses = 0;
      const keys = new Set([...Object.keys(p.features), ...Object.keys(features)]);
      keys.forEach((k) => {
        const a = rank(features[k]);
        const b = rank(p.features[k]);
        if (b > a) gains += 1;
        else if (b < a) losses += 1;
      });
      const current = p.id === planId;
      const delta = current
        ? trialing
          ? "Same features as your trial"
          : "Your current tier"
        : [gains ? `Adds ${gains} feature${gains === 1 ? "" : "s"}` : null, losses ? `drops ${losses}` : null]
            .filter(Boolean)
            .join(", ")
            .replace(/^drops/, "Drops") || "Same features";
      return {
        id: p.id,
        name: p.display_name,
        price: p.monthly_usd,
        slotPrice: p.extra_slot_monthly_usd,
        cta: current && trialing ? `Keep ${p.display_name}` : `Continue with ${p.display_name}`,
        delta,
        current,
      };
    });
}

export type ChargeLine = { label: string; amount: number };
export type ChargeEstimate = {
  kind: "scheduled" | "free" | "none" | "unknown";
  heading: string;
  total: number | null;
  date: string | null;
  dateLabel: string | null;
  lines: ChargeLine[];
  note: string;
};

export function chargeEstimate(
  ent: Pick<EntitlementsOut, "plan_id" | "subscription_status" | "extra_project_slots" | "trial_ends_at" | "current_period_end">,
  catalog: BillingPlansCatalog | null | undefined,
): ChargeEstimate {
  const status = (ent.subscription_status || "").toLowerCase();
  if (isInternalPlan(ent.plan_id)) {
    return {
      kind: "none",
      heading: "Not billed",
      total: null,
      date: null,
      dateLabel: null,
      lines: [],
      note: "Internal workspaces have no Stripe subscription and no scheduled charge.",
    };
  }
  if (status === "canceled" || status === "expired") {
    return {
      kind: "none",
      heading: "No upcoming charge",
      total: null,
      date: formatBillingDate(ent.current_period_end),
      dateLabel: ent.current_period_end ? "Access ends" : null,
      lines: [],
      note: "Stripe will not bill this workspace again unless you start a plan.",
    };
  }
  const plan = findPlan(catalog, ent.plan_id);
  if (!plan || plan.monthly_usd == null) {
    return {
      kind: "unknown",
      heading: "Next charge",
      total: null,
      date: formatBillingDate(status === "trialing" ? ent.trial_ends_at : ent.current_period_end),
      dateLabel: status === "trialing" ? "Trial ends" : "Renews",
      lines: [],
      note: "List prices did not load, so no estimate is shown. Your Stripe invoice has the exact amount.",
    };
  }
  if (plan.monthly_usd === 0 && !ent.extra_project_slots) {
    return {
      kind: "free",
      heading: "No recurring charge",
      total: 0,
      date: null,
      dateLabel: null,
      lines: [{ label: `${plan.display_name} plan`, amount: 0 }],
      note: `${plan.display_name} costs ${formatUsd(0)} a month. Paid add-ons need a paid plan.`,
    };
  }
  const lines: ChargeLine[] = [{ label: `${plan.display_name} plan`, amount: plan.monthly_usd }];
  const slots = ent.extra_project_slots || 0;
  if (slots > 0 && plan.extra_slot_monthly_usd != null) {
    lines.push({
      label: `${slots} extra project slot${slots === 1 ? "" : "s"} at ${formatUsd(plan.extra_slot_monthly_usd, { whole: true })}`,
      amount: slots * plan.extra_slot_monthly_usd,
    });
  }
  const total = lines.reduce((sum, l) => sum + l.amount, 0);
  if (status === "past_due" || status === "unpaid") {
    return {
      kind: "scheduled",
      heading: "Unpaid invoice",
      total,
      date: formatBillingDate(ent.current_period_end),
      dateLabel: ent.current_period_end ? "Due since" : null,
      lines,
      note: "Estimate of the unpaid renewal from list prices. Stripe holds the real invoice and retries the card.",
    };
  }
  const trialing = status === "trialing";
  const iso = trialing ? ent.trial_ends_at : ent.current_period_end;
  return {
    kind: "scheduled",
    heading: trialing ? `To keep ${plan.display_name}` : "Next charge",
    total,
    date: formatBillingDate(iso),
    dateLabel: iso ? (trialing ? "Trial ends" : "Renews") : null,
    lines,
    note: trialing
      ? "Trials start without a card, so nothing is scheduled. Stripe charges only after you confirm checkout. List prices; the invoice is final."
      : ESTIMATE_NOTE,
  };
}

export type SlotMeter = {
  used: number;
  limit: number | null;
  purchased: number;
  ratio: number;
  atLimit: boolean;
  label: string;
  hint: string | null;
};

export function slotMeter(
  ent: Pick<EntitlementsOut, "active_projects" | "active_project_limit" | "extra_project_slots">,
  opts: { slotsOffered?: boolean } = {},
): SlotMeter {
  const slotsOffered = opts.slotsOffered ?? true;
  const used = Math.max(0, ent.active_projects || 0);
  const limit = ent.active_project_limit;
  const purchased = Math.max(0, ent.extra_project_slots || 0);
  if (limit == null) {
    return { used, limit: null, purchased, ratio: 0, atLimit: false, label: `${used} active, no limit`, hint: null };
  }
  const ratio = limit > 0 ? Math.min(1, used / limit) : 1;
  const atLimit = used >= limit;
  const label = `${used} of ${limit} active`;
  const hint = atLimit
    ? slotsOffered
      ? "At your limit. Archive a project or add a slot before starting another."
      : "At your limit. Archive a project or move to a paid plan before starting another."
    : null;
  return { used, limit, purchased, ratio, atLimit, label, hint };
}

export type FeatureValue = { text: string; included: boolean };

export function featureValue(raw: string | undefined): FeatureValue {
  if (raw == null || raw === "" || raw === "false" || raw === "0") return { text: "Not included", included: false };
  if (raw === "true") return { text: "Included", included: true };
  if (raw === "unlimited") return { text: "Unlimited", included: true };
  return { text: raw, included: true };
}

function rank(v: string | undefined): number {
  if (v === "unlimited") return Number.POSITIVE_INFINITY;
  if (v === "true") return 1;
  if (v == null || v === "false" || v === "") return 0;
  const n = Number(v);
  return Number.isFinite(n) ? n : 1;
}

export type EntitlementRow = {
  key: string;
  label: string;
  current: FeatureValue;
  next: FeatureValue | null;
  gain: boolean;
};

const FALLBACK_FEATURES: Array<{ key: string; label: string }> = [
  { key: "connections_limit", label: "Odoo connections" },
  { key: "active_projects_limit", label: "Active projects" },
  { key: "designer", label: "View designer" },
  { key: "automations", label: "Automations" },
  { key: "module_export", label: "Module export + sandbox" },
  { key: "bulk_suite", label: "Bulk suite" },
  { key: "expert", label: "Odoo Expert" },
  { key: "dev_tools", label: "Code Studio and developer tools" },
];

/** Names for registry keys outside the catalog's display list (apps/api/app/entitlements.py FEATURE_KEYS). */
const EXTRA_LABELS: Record<string, string> = {
  approvals: "Approvals",
  reports_designer: "Report designer",
  import: "Data import",
  ai_draft: "Draft Studio (AI)",
  sandbox: "Sandbox",
  snapshots_full: "Full snapshots",
  id_generator: "ID generator",
  power_ops: "Power operations",
  health_check: "Health checks",
  pipelines: "Pipelines",
  audit_export: "Audit export",
  store_packaging: "App store packaging",
  migration_assist: "Migration assist",
  bulk_security: "Bulk security",
  api_keys: "API keys",
  white_label: "White label",
  workspaces_multi: "Multiple workspaces",
};

export function featureLabel(key: string, catalog?: BillingPlansCatalog | null): string {
  const hit = catalog?.display_features.find((f) => f.key === key) ?? FALLBACK_FEATURES.find((f) => f.key === key);
  const label =
    hit?.label ?? EXTRA_LABELS[key] ?? key.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
  return label.replace(/ & /g, " and ");
}

/** Rows for "What your plan includes": current from entitlements (overrides included), next from the catalog. */
export function entitlementRows(
  features: Record<string, string>,
  catalog: BillingPlansCatalog | null | undefined,
  next: BillingPlanRow | null,
): EntitlementRow[] {
  const keys = catalog?.display_features?.length ? catalog.display_features : FALLBACK_FEATURES;
  return keys.map(({ key }) => {
    const cur = features[key];
    const nxt = next ? next.features[key] : undefined;
    return {
      key,
      label: featureLabel(key, catalog),
      current: featureValue(cur),
      next: next ? featureValue(nxt) : null,
      gain: next ? rank(nxt) > rank(cur) : false,
    };
  });
}

export type LostFeature = { feature_key: string; from: string; to: string };

export function downgradeRows(lost: LostFeature[], catalog?: BillingPlansCatalog | null) {
  return lost.map((f) => ({
    key: f.feature_key,
    label: featureLabel(f.feature_key, catalog),
    from: featureValue(f.from).text,
    to: featureValue(f.to).text,
  }));
}

export type RiskNotice = { id: "trial" | "payment" | "incomplete"; tone: "warning" | "danger"; guide: BillingGuide };

/** Amber or red only where money or access is actually at risk. Healthy plans get no banner. */
export function riskNotices(
  ent: Pick<EntitlementsOut, "plan_id" | "subscription_status" | "trial_ends_at">,
  catalog?: BillingPlansCatalog | null,
  now: number = Date.now(),
): RiskNotice[] {
  const out: RiskNotice[] = [];
  const status = (ent.subscription_status || "").toLowerCase();
  const name = planDisplayName(ent.plan_id, catalog);
  if (status === "past_due" || status === "unpaid") {
    out.push({
      id: "payment",
      tone: "danger",
      guide: {
        title: status === "unpaid" ? "Invoice unpaid. Build features may lock." : "Last payment failed",
        why: `Stripe could not charge the card on file for ${name}. Stripe retries on its own schedule, and Ingenium mirrors the result.`,
        next: "Update the payment method in Stripe. The status here refreshes once Stripe confirms payment.",
      },
    });
  }
  if (status === "incomplete") {
    out.push({
      id: "incomplete",
      tone: "warning",
      guide: {
        title: "Checkout did not finish",
        why: "Stripe has the subscription on hold until the first payment completes. Nothing extra is unlocked yet.",
        next: "Open Manage plan to finish payment in Stripe, or pick another tier.",
      },
    });
  }
  const days = daysUntil(ent.trial_ends_at, now);
  if (status === "trialing" && days != null && days >= 0 && days <= 3) {
    const when = days === 0 ? "today" : days === 1 ? "in 1 day" : `in ${days} days`;
    out.push({
      id: "trial",
      tone: "warning",
      guide: {
        title: `Trial ends ${when}`,
        why: `The trial unlocks ${name} features until ${formatBillingDate(ent.trial_ends_at)}. Keeping them after that needs a paid plan.`,
        next: "Choose a plan before the trial ends. Stripe charges only when you confirm checkout.",
      },
    });
  }
  return out;
}

export function returnNotice(params: { upgraded?: boolean; slots?: boolean }): BillingGuide | null {
  if (params.slots) {
    return {
      title: "Slot checkout complete",
      why: "Stripe confirms new slots by webhook, usually within a minute. The meter shows what Ingenium has on record.",
      next: "Refresh the plan if the slot count has not moved yet.",
    };
  }
  if (params.upgraded) {
    return {
      title: "Checkout complete",
      why: "Stripe confirms plan changes by webhook, usually within a minute. The plan below is what Ingenium has on record.",
      next: "Refresh the plan if it still shows the old tier.",
    };
  }
  return null;
}

export type BillingErrorContext = "portal" | "checkout" | "load";

export function billingErrorGuide(context: BillingErrorContext, rawMessage?: string): BillingGuide {
  const detail = sanitizeBillingCopy((rawMessage || "").trim());
  const m = detail.toLowerCase();
  if (/no billing customer/.test(m)) {
    return {
      title: "No Stripe customer on file yet",
      why: "Stripe creates a customer at the first paid checkout. This workspace has not checked out, so there are no invoices or saved card.",
      next: "Pick a paid plan with Manage plan, or compare plans first.",
    };
  }
  if (/stripe.*(not configured|missing|secret)|not configured/.test(m)) {
    return {
      title: context === "checkout" ? "Checkout is not available" : "Stripe portal is not available",
      why: "This Ingenium server has no Stripe keys configured, so it cannot open Stripe.",
      next: "Ask the workspace owner to configure Stripe, then try again.",
    };
  }
  if (/\b40[13]\b|forbidden|admin|permission|not allowed/.test(m)) {
    return {
      title: "Only a workspace admin can change billing",
      why: "Stripe sessions are limited to admins of this workspace.",
      next: "Ask an admin to open Manage plan, or to raise your role.",
    };
  }
  if (/failed to fetch|network|timed? ?out|timeout|\b50[234]\b|unreachable/.test(m)) {
    return {
      title: context === "load" ? "Could not load your plan" : "Could not reach Stripe",
      why: "The Ingenium API did not answer in time.",
      next: "Check the connection, then try again.",
    };
  }
  const base: Record<BillingErrorContext, BillingGuide> = {
    portal: {
      title: "Could not open the Stripe portal",
      why: detail ? `The billing API refused the request. Detail: ${detail}` : "The billing API refused the request.",
      next: "Try again. If it keeps failing, use Diagnose with Expert.",
    },
    checkout: {
      title: "Could not start checkout",
      why: detail ? `The billing API refused the request. Detail: ${detail}` : "The billing API refused the request.",
      next: "Try again, or compare plans and pick another tier.",
    },
    load: {
      title: "Could not load your plan",
      why: detail ? `Detail: ${detail}` : "The entitlements request failed.",
      next: "Try again. Billing in Stripe is unaffected.",
    },
  };
  return base[context];
}

/** Tier list for the rail: real list prices in catalog order, current plan marked. */
export function tierLadder(catalog: BillingPlansCatalog | null | undefined, currentId: string | null | undefined) {
  if (!catalog) return [];
  return catalog.tier_order
    .map((id) => findPlan(catalog, id))
    .filter((p): p is BillingPlanRow => Boolean(p))
    .map((p) => ({
      id: p.id,
      name: p.display_name,
      price: p.monthly_usd,
      slotPrice: p.extra_slot_monthly_usd,
      current: p.id === currentId,
    }));
}
