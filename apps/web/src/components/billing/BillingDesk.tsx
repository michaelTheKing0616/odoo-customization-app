"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { AlertTriangle, Check, CheckCircle2, Copy, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { EmptyState, Skeleton } from "@/components/ui/layout-primitives";
import type { BillingPlansCatalog, EntitlementsOut } from "@/lib/api";
import { diagnoseWithExpert } from "@/lib/expert-diagnostics";
import {
  ADD_SLOT_CTA,
  BILLING_CTA,
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  billingErrorGuide,
  chargeEstimate,
  chooserTiers,
  daysUntil,
  downgradeRows,
  entitlementRows,
  findPlan,
  formatBillingDate,
  formatUsd,
  isFreePlan,
  isInternalPlan,
  nextTier,
  planDisplayName,
  primaryAction,
  relativeDays,
  returnNotice,
  riskNotices,
  sanitizeBillingCopy,
  slotMeter,
  statusMeta,
  tierLadder,
  type BillingErrorContext,
  type BillingGuide,
  type LostFeature,
} from "@/lib/billingScreen";
import { FrameMeta } from "@/components/frame/FrameMeta";

/** Styles live in ./billing-desk.css, imported by the route and the harness. */
export type BillingView = "loading" | "ready" | "empty" | "error";

export type BillingActionError = {
  context: Exclude<BillingErrorContext, "load">;
  /** Where the error shows: next to the action that caused it. */
  source: "plan" | "billing";
  message: string;
};

export type BillingDeskProps = {
  view: BillingView;
  data: EntitlementsOut | null;
  catalog: BillingPlansCatalog | null;
  catalogLoading?: boolean;
  lostFeatures?: LostFeature[];
  loadError?: string | null;
  returned?: { upgraded?: boolean; slots?: boolean };
  actionError?: BillingActionError | null;
  portalBusy?: "plan" | "billing" | null;
  checkoutBusy?: string | null;
  defaultChooserOpen?: boolean;
  now?: number;
  onManagePlan?: () => void;
  onManageBilling?: () => void;
  onCheckout?: (planId: string) => void;
  onAddSlot?: () => void;
  onRetry?: () => void;
  onRefresh?: () => void;
  onDismissError?: () => void;
};

export function BillingDesk(props: BillingDeskProps) {
  const { view, data, catalog } = props;
  const now = props.now ?? Date.now();
  const [chooserOpen, setChooserOpen] = useState(Boolean(props.defaultChooserOpen));
  const chooserRef = useRef<HTMLDivElement>(null);
  const chooserId = useId();

  const ready = view === "ready" && data != null;
  const action = ready ? primaryAction(data.plan_id, data.subscription_status, catalog) : null;
  const risks = ready ? riskNotices(data, catalog, now) : [];
  const back = returnNotice(props.returned ?? {});

  function openChooser() {
    setChooserOpen(true);
    requestAnimationFrame(() => {
      chooserRef.current?.querySelector<HTMLButtonElement>("button")?.focus({ preventScroll: true });
      chooserRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
  }

  function onPrimary() {
    if (!action) return;
    if (action.kind === "picker") {
      if (chooserOpen) setChooserOpen(false);
      else openChooser();
      return;
    }
    if (action.kind === "portal") props.onManagePlan?.();
  }

  return (
    <div className="billing-desk" data-testid="billing-page" data-view={view} data-plan={data?.plan_id ?? ""}>
      <header className="bd-head studio-bar-dark">
        <div className="bd-head-copy">
          <FrameMeta />
          <h1 className="bd-title">{PAGE_TITLE}</h1>
          <p className="bd-lead">{PAGE_DESCRIPTION}</p>
        </div>
        {ready ? <HeadMeta data={data} /> : null}
      </header>

      {back && ready ? (
        <div className="bd-note" data-tone="success" role="status" data-testid="billing-return-note">
          <CheckCircle2 className="bd-note-icon" aria-hidden />
          <div className="bd-note-body">
            <p className="bd-note-title">{back.title}</p>
            <p className="bd-note-text">{back.why}</p>
          </div>
          {props.onRefresh ? (
            <Button variant="ghost" size="sm" onClick={props.onRefresh} className="bd-note-action">
              Refresh plan
            </Button>
          ) : null}
        </div>
      ) : null}

      {risks.map((r) => (
        <div
          key={r.id}
          className="bd-note"
          data-tone={r.tone}
          role={r.tone === "danger" ? "alert" : "status"}
          data-testid={r.id === "trial" ? "trial-banner" : `billing-risk-${r.id}`}
        >
          <AlertTriangle className="bd-note-icon" aria-hidden />
          <div className="bd-note-body">
            <p className="bd-note-title">{sanitizeBillingCopy(r.guide.title)}</p>
            <p className="bd-note-text">
              {sanitizeBillingCopy(r.guide.why)} {sanitizeBillingCopy(r.guide.next)}
            </p>
          </div>
          {r.id === "payment" ? (
            <Button
              variant="secondary"
              size="sm"
              className="bd-note-action"
              onClick={props.onManageBilling}
              loading={props.portalBusy === "billing"}
            >
              Update payment method
            </Button>
          ) : r.id === "trial" && action?.kind === "picker" ? (
            <Button variant="secondary" size="sm" className="bd-note-action" onClick={openChooser}>
              Choose a plan
            </Button>
          ) : null}
        </div>
      ))}

      <div className="bd-grid" data-has-rail={ready ? "full" : "lite"}>
        <div className="bd-main">
          <section
            className="bd-paper bd-sheet"
            aria-labelledby="bd-plan-title"
            data-testid="billing-plan-sheet"
            aria-busy={view === "loading" || undefined}
          >
            {view === "loading" ? (
              <div role="status" data-testid="billing-plan-loading" className="bd-sheet-loading">
                <span className="sr-only">Loading your plan.</span>
                <div aria-hidden className="bd-skel-stack">
                  <div className="bd-skel-row">
                    <Skeleton className="h-8 w-40" />
                    <Skeleton className="h-8 w-28" />
                  </div>
                  <Skeleton className="h-14 w-full" />
                  <Skeleton className="h-6 w-full" />
                  <Skeleton className="h-9 w-72 max-w-full" />
                </div>
              </div>
            ) : view === "error" ? (
              <LoadError message={props.loadError ?? ""} onRetry={props.onRetry} />
            ) : ready ? (
              <PlanSheet
                data={data}
                catalog={catalog}
                catalogLoading={props.catalogLoading}
                now={now}
                actionLabel={action!.label}
                actionHint={action!.hint}
                actionKind={action!.kind}
                chooserOpen={chooserOpen}
                chooserId={chooserId}
                portalBusy={props.portalBusy === "plan"}
                onPrimary={onPrimary}
                onAddSlot={props.onAddSlot}
                error={props.actionError?.source === "plan" ? props.actionError : null}
                onDismissError={props.onDismissError}
                onOpenChooser={openChooser}
              >
                {action!.kind === "picker" && chooserOpen ? (
                  <PlanChooser
                    ref={chooserRef}
                    id={chooserId}
                    data={data}
                    catalog={catalog}
                    busyId={props.checkoutBusy ?? null}
                    onCheckout={props.onCheckout}
                  />
                ) : null}
              </PlanSheet>
            ) : (
              <div className="bd-sheet-empty">
                <h2 id="bd-plan-title" className="sr-only">
                  Plan
                </h2>
                <EmptyState
                  title="No plan to show"
                  description="Your plan, status, and project slots appear here after you sign in with an account."
                  action={
                    <Button asChild variant="secondary" size="sm">
                      <Link href="/login">Sign in</Link>
                    </Button>
                  }
                />
              </div>
            )}
          </section>

          {view === "loading" ? (
            <div className="bd-panel bd-includes" aria-hidden>
              <div className="bd-skel-stack">
                <Skeleton className="h-4 w-48" />
                {Array.from({ length: 6 }, (_, i) => (
                  <Skeleton key={i} className="h-6 w-full" />
                ))}
              </div>
            </div>
          ) : null}
          {ready ? <IncludesTable data={data} catalog={catalog} /> : null}
        </div>

        <div className="bd-rail">
          {view === "loading" ? (
            <div className="bd-paper bd-charge" aria-hidden>
              <div className="bd-skel-stack">
                <Skeleton className="h-3 w-24" />
                <Skeleton className="h-8 w-32" />
                <Skeleton className="h-16 w-full" />
              </div>
            </div>
          ) : null}
          {ready ? (
            <>
              <ChargeCard data={data} catalog={catalog} />
              <DowngradePanel data={data} catalog={catalog} lost={props.lostFeatures ?? []} />
              <PaymentPanel
                busy={props.portalBusy === "billing"}
                onManageBilling={props.onManageBilling}
                error={props.actionError?.source === "billing" ? props.actionError : null}
                onDismissError={props.onDismissError}
                onOpenChooser={action?.kind === "picker" ? openChooser : undefined}
              />
            </>
          ) : null}
          {view !== "loading" ? (
            <PlansLadder catalog={catalog} currentId={ready ? data.plan_id : null} loading={props.catalogLoading} />
          ) : null}
        </div>
      </div>
    </div>
  );
}

function HeadMeta({ data }: { data: EntitlementsOut }) {
  const meta = statusMeta(data.subscription_status);
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const t = setTimeout(() => setCopied(false), 1600);
    return () => clearTimeout(t);
  }, [copied]);
  return (
    <div className="bd-head-meta">
      <span className="bd-chip" data-tone={meta.tone} data-testid="billing-status-chip" title={meta.hint}>
        <span className="bd-chip-dot" aria-hidden />
        {meta.label}
      </span>
      <button
        type="button"
        className="bd-ws"
        onClick={() => {
          void navigator.clipboard?.writeText(data.workspace_id).catch(() => undefined);
          setCopied(true);
        }}
        aria-label={copied ? "Workspace ID copied" : `Copy workspace ID ${data.workspace_id}`}
        data-testid="billing-workspace-id"
      >
        <span className="bd-ws-label">Workspace</span>
        <code translate="no">{data.workspace_id}</code>
        <span className="bd-ws-icon" data-copied={copied || undefined} aria-hidden>
          {copied ? <Check /> : <Copy />}
        </span>
      </button>
      <span className="sr-only" aria-live="polite">
        {copied ? "Workspace ID copied." : ""}
      </span>
    </div>
  );
}

type PlanSheetProps = {
  data: EntitlementsOut;
  catalog: BillingPlansCatalog | null;
  catalogLoading?: boolean;
  now: number;
  actionLabel: string;
  actionHint: string;
  actionKind: "portal" | "picker" | "none";
  chooserOpen: boolean;
  chooserId: string;
  portalBusy: boolean;
  onPrimary: () => void;
  onAddSlot?: () => void;
  error: BillingActionError | null;
  onDismissError?: () => void;
  onOpenChooser: () => void;
  children?: React.ReactNode;
};

function PlanSheet(p: PlanSheetProps) {
  const { data, catalog } = p;
  const plan = findPlan(catalog, data.plan_id);
  const name = planDisplayName(data.plan_id, catalog);
  const internal = isInternalPlan(data.plan_id);
  const meta = statusMeta(data.subscription_status);
  const free = isFreePlan(data.plan_id, catalog);
  const meter = slotMeter(data, { slotsOffered: plan?.extra_slot_monthly_usd != null });
  const status = (data.subscription_status || "").toLowerCase();
  const trialing = status === "trialing";
  const periodDate = formatBillingDate(data.current_period_end);
  const periodRel = relativeDays(daysUntil(data.current_period_end, p.now));
  const trialDate = formatBillingDate(data.trial_ends_at);
  const trialRel = relativeDays(daysUntil(data.trial_ends_at, p.now));
  const canAddSlot = plan?.extra_slot_monthly_usd != null && status !== "canceled";

  return (
    <>
      <div className="bd-sheet-top">
        <div className="bd-plan">
          <h2 id="bd-plan-title" className="bd-plan-name" data-testid="billing-plan-name">
            {name}
          </h2>
          <p className="bd-plan-sub">
            <code translate="no">{data.plan_id}</code>
            <span>
              {internal
                ? "Not billed"
                : trialing
                  ? "Trial, no card required"
                  : free
                    ? "Free tier, no card needed"
                    : "Billed monthly through Stripe"}
            </span>
          </p>
        </div>
        <div className="bd-price" data-testid="billing-plan-price">
          {internal ? (
            <>
              <span className="bd-price-amount">{formatUsd(0, { whole: true })}</span>
              <span className="bd-price-unit">Internal workspace</span>
            </>
          ) : plan?.monthly_usd != null ? (
            <>
              <span className="bd-price-amount">{formatUsd(plan.monthly_usd, { whole: true })}</span>
              <span className="bd-price-unit">per month, list price</span>
            </>
          ) : (
            <>
              <span className="bd-price-amount bd-price-amount--muted">{p.catalogLoading ? "Fetching prices" : "Unavailable"}</span>
              <span className="bd-price-unit">
                {p.catalogLoading ? "Fetching list prices" : "List prices did not load"}
              </span>
            </>
          )}
        </div>
      </div>

      <dl className="bd-ledger">
        <div className="bd-ledger-cell">
          <dt>Status</dt>
          <dd>{meta.label}</dd>
          <dd className="bd-ledger-sub">
            {free && status === "active" ? "Free tier. There is no Stripe subscription behind it." : meta.hint}
          </dd>
        </div>
        {trialing ? (
          <div className="bd-ledger-cell">
            <dt>Trial ends</dt>
            <dd>{trialDate ?? "Not set"}</dd>
            {trialRel ? <dd className="bd-ledger-sub">{trialRel}</dd> : null}
          </div>
        ) : (
          <div className="bd-ledger-cell">
            <dt>
              {status === "canceled"
                ? "Access ends"
                : status === "past_due" || status === "unpaid"
                  ? "Payment due"
                  : "Renews"}
            </dt>
            <dd>{periodDate ?? (internal || free ? "No renewal" : "Not reported")}</dd>
            <dd className="bd-ledger-sub">
              {periodRel ??
                (internal ? "No billing period" : free ? `${name} never bills` : "Stripe has not sent a period end")}
            </dd>
          </div>
        )}
        <div className="bd-ledger-cell">
          <dt>Extra slot</dt>
          <dd>{plan?.extra_slot_monthly_usd != null ? `${formatUsd(plan.extra_slot_monthly_usd, { whole: true })} a month` : "Not offered"}</dd>
          <dd className="bd-ledger-sub">
            {plan?.extra_slot_monthly_usd != null ? "Per active project above the base" : `Not on ${name}`}
          </dd>
        </div>
      </dl>

      <div className="bd-meter" data-at-limit={meter.atLimit || undefined} data-testid="billing-slot-meter">
        <div className="bd-meter-head">
          <span className="bd-meter-label">Active projects</span>
          <span className="bd-meter-value">
            {meter.label}
            {meter.purchased > 0 ? <span className="bd-meter-extra">includes {meter.purchased} purchased</span> : null}
          </span>
        </div>
        {meter.limit != null ? (
          <div
            className="bd-meter-track"
            role="meter"
            aria-label="Active project slots used"
            aria-valuemin={0}
            aria-valuemax={meter.limit}
            aria-valuenow={Math.min(meter.used, meter.limit)}
            aria-valuetext={meter.label}
          >
            <span className="bd-meter-fill" style={{ transform: `scaleX(${meter.ratio})` }} />
          </div>
        ) : (
          <p className="bd-meter-free">No project limit on {name}.</p>
        )}
        {meter.hint ? <p className="bd-meter-hint">{meter.hint}</p> : null}
      </div>

      <div className="bd-actions">
        <div className="bd-actions-row">
          <Button
            variant="primary"
            onClick={p.onPrimary}
            disabled={p.actionKind === "none"}
            loading={p.portalBusy}
            aria-expanded={p.actionKind === "picker" ? p.chooserOpen : undefined}
            aria-controls={p.actionKind === "picker" && p.chooserOpen ? p.chooserId : undefined}
            aria-describedby="bd-primary-hint"
            data-testid="billing-manage-plan"
          >
            {p.portalBusy ? "Opening Stripe…" : p.actionLabel}
            {p.actionKind === "portal" && !p.portalBusy ? <ExternalLink className="bd-btn-icon" aria-hidden /> : null}
          </Button>
          {canAddSlot ? (
            <Button variant="secondary" onClick={p.onAddSlot} data-testid="open-upgrade">
              {ADD_SLOT_CTA}
            </Button>
          ) : null}
          <Link href="/pricing" className="bd-link" data-testid="pricing-link">
            Compare plans
          </Link>
        </div>
        <p id="bd-primary-hint" className="bd-hint">
          {p.actionHint}
        </p>
        {p.error ? (
          <ActionError error={p.error} onDismiss={p.onDismissError} onOpenChooser={p.onOpenChooser} />
        ) : null}
      </div>

      {p.children}
    </>
  );
}

type PlanChooserProps = {
  id: string;
  data: EntitlementsOut;
  catalog: BillingPlansCatalog | null;
  busyId: string | null;
  onCheckout?: (planId: string) => void;
  ref?: React.Ref<HTMLDivElement>;
};

function PlanChooser({ id, data, catalog, busyId, onCheckout, ref }: PlanChooserProps) {
  const tiers = chooserTiers(catalog, data.plan_id, data.features, data.subscription_status);
  return (
    <div className="bd-chooser" id={id} ref={ref} data-testid="billing-plan-chooser">
      <div className="bd-chooser-head">
        <h3 className="bd-h3">Choose a plan</h3>
        <p className="bd-chooser-sub">Monthly list prices. Stripe shows tax and the exact total before you pay.</p>
      </div>
      {tiers.length === 0 ? (
        <p className="bd-chooser-sub">List prices did not load. Compare plans on the pricing page instead.</p>
      ) : (
        <ul className="bd-chooser-list">
          {tiers.map((t) => (
            <li key={t.id} className="bd-chooser-row" data-current={t.current || undefined}>
              <div className="bd-chooser-name">
                <span>{t.name}</span>
                <span className="bd-chooser-delta">{t.delta}</span>
              </div>
              <div className="bd-chooser-price">
                <span>{formatUsd(t.price, { whole: true })}</span>
                <span className="bd-chooser-unit">a month</span>
              </div>
              <Button
                variant="secondary"
                size="sm"
                loading={busyId === t.id}
                disabled={busyId != null && busyId !== t.id}
                onClick={() => onCheckout?.(t.id)}
                data-testid={`billing-choose-${t.id}`}
              >
                {busyId === t.id ? "Opening Stripe…" : t.cta}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ChargeCard({ data, catalog }: { data: EntitlementsOut; catalog: BillingPlansCatalog | null }) {
  const est = chargeEstimate(data, catalog);
  return (
    <section className="bd-paper bd-charge" aria-labelledby="bd-charge-title" data-testid="billing-charge" data-kind={est.kind}>
      <h2 id="bd-charge-title" className="bd-kicker-title">
        {est.heading}
      </h2>
      <p className="bd-charge-total" data-muted={est.total == null || undefined}>
        {est.total != null ? formatUsd(est.total) : est.kind === "none" ? formatUsd(0) : "Unavailable"}
      </p>
      {est.date ? (
        <p className="bd-charge-date">
          {est.dateLabel} {est.date}
        </p>
      ) : null}
      {est.lines.length > 0 ? (
        <dl className="bd-lines">
          {est.lines.map((l) => (
            <div key={l.label} className="bd-line">
              <dt>{l.label}</dt>
              <dd>{formatUsd(l.amount)}</dd>
            </div>
          ))}
          {est.lines.length > 1 ? (
            <div className="bd-line bd-line--total">
              <dt>Monthly total</dt>
              <dd>{formatUsd(est.total)}</dd>
            </div>
          ) : null}
        </dl>
      ) : null}
      <p className="bd-fine">{est.note}</p>
    </section>
  );
}

function IncludesTable({ data, catalog }: { data: EntitlementsOut; catalog: BillingPlansCatalog | null }) {
  const name = planDisplayName(data.plan_id, catalog);
  const next = nextTier(catalog, data.plan_id);
  const rows = entitlementRows(data.features, catalog, next);
  return (
    <section className="bd-panel bd-includes" aria-labelledby="bd-includes-title" data-testid="billing-includes">
      <div className="bd-panel-head">
        <h2 id="bd-includes-title" className="bd-h2">
          What your plan includes
        </h2>
        <p className="bd-panel-sub">
          {next
            ? `Your workspace entitlements next to ${next.display_name}, the next tier up.`
            : "Your workspace entitlements, including any overrides."}
        </p>
      </div>
      <div className="bd-table-wrap">
        <table className="bd-table">
          <thead>
            <tr>
              <th scope="col">Feature</th>
              <th scope="col">
                {name}
                <span className="bd-th-tag">Yours</span>
              </th>
              {next ? (
                <th scope="col">
                  {next.display_name}
                  <span className="bd-th-sub">{formatUsd(next.monthly_usd, { whole: true })} a month</span>
                </th>
              ) : null}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key} data-gain={r.gain || undefined}>
                <th scope="row">{r.label}</th>
                <td data-included={r.current.included || undefined}>{r.current.text}</td>
                {r.next ? (
                  <td data-included={r.next.included || undefined} data-gain={r.gain || undefined}>
                    {r.gain ? (
                      <>
                        <span className="bd-gain" aria-hidden>
                          +
                        </span>
                        <span className="sr-only">Gains </span>
                      </>
                    ) : null}
                    {r.next.text}
                  </td>
                ) : null}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function DowngradePanel({
  data,
  catalog,
  lost,
}: {
  data: EntitlementsOut;
  catalog: BillingPlansCatalog | null;
  lost: LostFeature[];
}) {
  if (isInternalPlan(data.plan_id) || data.plan_id === "free_solo") return null;
  const rows = downgradeRows(lost, catalog);
  const target = planDisplayName("free_solo", catalog);
  return (
    <section className="bd-panel bd-downgrade" aria-labelledby="bd-down-title" data-testid="downgrade-summary">
      <h2 id="bd-down-title" className="bd-h3">
        If you move to {target}
      </h2>
      {rows.length > 0 ? (
        <ul className="bd-loss-list">
          {rows.slice(0, 8).map((r) => (
            <li key={r.key}>
              <span className="bd-loss-sign" aria-hidden>
                −
              </span>
              <span className="bd-loss-label">{r.label}</span>
              <span className="bd-loss-change">
                {r.from} <span className="sr-only">changes</span>
                <span aria-hidden> to </span>
                {r.to}
              </span>
            </li>
          ))}
          {rows.length > 8 ? <li className="bd-loss-more">and {rows.length - 8} more build features</li> : null}
        </ul>
      ) : (
        <p className="bd-panel-sub">The feature comparison did not load. The plan itself is unchanged.</p>
      )}
      <p className="bd-fine">
        Build features lock again. Operate tools stay available, and your connections and project history remain.
      </p>
    </section>
  );
}

function PaymentPanel({
  busy,
  onManageBilling,
  error,
  onDismissError,
  onOpenChooser,
}: {
  busy: boolean;
  onManageBilling?: () => void;
  error: BillingActionError | null;
  onDismissError?: () => void;
  onOpenChooser?: () => void;
}) {
  return (
    <section className="bd-panel bd-payment" aria-labelledby="bd-pay-title" data-testid="billing-payment">
      <h2 id="bd-pay-title" className="bd-h3">
        Payment and invoices
      </h2>
      <p className="bd-panel-sub">Card, invoices, and receipts live in Stripe. Card details are entered on Stripe, not in Ingenium.</p>
      <Button
        variant="secondary"
        size="sm"
        onClick={onManageBilling}
        loading={busy}
        data-testid="billing-manage-billing"
        className="bd-pay-btn"
      >
        {busy ? "Opening Stripe…" : BILLING_CTA}
        {!busy ? <ExternalLink className="bd-btn-icon" aria-hidden /> : null}
      </Button>
      {error ? <ActionError error={error} onDismiss={onDismissError} onOpenChooser={onOpenChooser} /> : null}
    </section>
  );
}

function PlansLadder({
  catalog,
  currentId,
  loading,
}: {
  catalog: BillingPlansCatalog | null;
  currentId: string | null;
  loading?: boolean;
}) {
  const tiers = tierLadder(catalog, currentId);
  return (
    <section className="bd-panel bd-plans" aria-labelledby="bd-plans-title" data-testid="billing-plans">
      <h2 id="bd-plans-title" className="bd-h3">
        Plans
      </h2>
      {tiers.length > 0 ? (
        <ul className="bd-ladder">
          {tiers.map((t) => (
            <li key={t.id} data-current={t.current || undefined}>
              <span className="bd-ladder-name">
                {t.name}
                {t.current ? <span className="bd-ladder-tag">Current</span> : null}
              </span>
              <span className="bd-ladder-price">
                {formatUsd(t.price, { whole: true })}
                <span className="bd-ladder-unit">/mo</span>
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="bd-panel-sub">{loading ? "Loading list prices…" : "List prices did not load."}</p>
      )}
      <p className="bd-fine">
        USD list prices from the Ingenium catalog.{" "}
        <Link href="/pricing" className="bd-link">
          Compare plans
        </Link>
      </p>
    </section>
  );
}

function ActionError({
  error,
  onDismiss,
  onOpenChooser,
}: {
  error: BillingActionError;
  onDismiss?: () => void;
  onOpenChooser?: () => void;
}) {
  const guide: BillingGuide = billingErrorGuide(error.context, error.message);
  const noCustomer = /no billing customer/i.test(error.message);
  return (
    <div className="bd-inline-error" role="alert" data-testid="billing-action-error">
      <p className="bd-inline-error-title">{sanitizeBillingCopy(guide.title)}</p>
      <p className="bd-inline-error-text">{sanitizeBillingCopy(guide.why)}</p>
      <p className="bd-inline-error-text">{sanitizeBillingCopy(guide.next)}</p>
      <div className="bd-inline-error-actions">
        {noCustomer && onOpenChooser ? (
          <Button variant="secondary" size="sm" onClick={onOpenChooser}>
            Choose a plan
          </Button>
        ) : null}
        {!noCustomer ? (
          <Button variant="ghost" size="sm" onClick={() => diagnoseWithExpert(error.message || guide.why)}>
            Diagnose with Expert
          </Button>
        ) : null}
        {onDismiss ? (
          <Button variant="ghost" size="sm" onClick={onDismiss}>
            Dismiss
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function LoadError({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const guide = billingErrorGuide("load", message);
  return (
    <div className="bd-load-error" data-testid="billing-plan-error">
      <h2 id="bd-plan-title" className="bd-h2">
        We couldn&apos;t load your plan.
      </h2>
      <p className="bd-panel-sub">{sanitizeBillingCopy(guide.why)}</p>
      <p className="bd-panel-sub">{sanitizeBillingCopy(guide.next)}</p>
      <div className="bd-inline-error-actions">
        <Button variant="secondary" size="sm" onClick={() => onRetry?.()}>
          Try again
        </Button>
        <Button variant="ghost" size="sm" onClick={() => diagnoseWithExpert(message || guide.why)}>
          Diagnose with Expert
        </Button>
      </div>
    </div>
  );
}
