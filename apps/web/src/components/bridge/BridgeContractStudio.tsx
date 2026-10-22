"use client";

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Tabs } from "@/components/ui/Tabs";
import { AlertTriangle, Check, ChevronRight, Copy, Lock, X } from "@/components/ui/icons";
import {
  DIRECTION_OPTIONS,
  EMPTY_FORM,
  ENTITY_NAME,
  HONESTY_LINE,
  IDEMPOTENCY_FIELD,
  PAGE_TITLE,
  POLICY_OPTIONS,
  PRIMARY_CTA,
  PRIMARY_CTA_BUSY,
  RESET_CTA,
  buildContract,
  buildLedger,
  classifyResult,
  directionLabel,
  firstErrorField,
  formsEqual,
  ledgerSummary,
  networkErrorGuide,
  overwriteRisk,
  previewJson,
  sanitizeCopy,
  statusChip,
  validateForm,
  type CheckRow,
  type ContractForm,
  type Direction,
  type FieldErrors,
  type FieldKey,
  type Outcome,
  type Policy,
  type TierResult,
} from "@/lib/bridgeContractScreen";
import { FrameMeta } from "@/components/frame/FrameMeta";

export type ValidateResponse = { status: number; body: TierResult | null };
export type ValidateFn = (contract: Record<string, unknown>) => Promise<ValidateResponse>;

export async function postTierI(contract: Record<string, unknown>): Promise<ValidateResponse> {
  const response = await fetch("/api/bridge/contracts/validate", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ contract }),
  });
  if (!response.ok) return { status: response.status, body: null };
  return { status: response.status, body: (await response.json()) as TierResult };
}

const TIME_FMT = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" });

function CheckGlyph({ status }: { status: CheckRow["status"] }) {
  return (
    <span className="br-glyph" data-status={status} aria-hidden>
      {status === "pass" ? <Check className="size-3" aria-hidden /> : null}
      {status === "fail" ? <X className="size-3" aria-hidden /> : null}
    </span>
  );
}

const STATUS_WORD: Record<CheckRow["status"], string> = {
  pass: "Passes",
  fail: "Fails",
  na: "Not applicable",
  wait: "Waiting",
  skip: "Not reached",
};

type Segment<T extends string> = { value: T; label: string };

function Segmented<T extends string>({
  name,
  label,
  labelId,
  value,
  options,
  onChange,
  testIdPrefix,
  invalid,
  describedBy,
  firstRef,
}: {
  name: string;
  label: string;
  labelId: string;
  value: T | "";
  options: Segment<T>[];
  onChange: (value: T) => void;
  testIdPrefix: string;
  invalid?: boolean;
  describedBy?: string;
  firstRef?: (el: HTMLInputElement | null) => void;
}) {
  return (
    <div
      className="br-seg"
      role="radiogroup"
      aria-labelledby={labelId}
      data-label={label}
      aria-invalid={invalid ? true : undefined}
      aria-describedby={describedBy}
      data-testid={testIdPrefix}
    >
      {options.map((opt, i) => (
        <label key={opt.value} className="br-seg-item" data-checked={value === opt.value ? "" : undefined}>
          <input
            type="radio"
            name={name}
            value={opt.value}
            checked={value === opt.value}
            onChange={() => onChange(opt.value)}
            ref={i === 0 ? firstRef : undefined}
            data-testid={`${testIdPrefix}-${opt.value}`}
          />
          <span>{opt.label}</span>
        </label>
      ))}
    </div>
  );
}

export type BridgeContractStudioProps = {
  initialForm?: ContractForm;
  initialOutcome?: Outcome | null;
  initialErrors?: FieldErrors;
  /** Harness only: render the in-flight state without a request. */
  initialPending?: boolean;
  initialCheckedAt?: Date | null;
  initialTab?: "contract" | "request";
  validateContract?: ValidateFn;
};

export function BridgeContractStudio({
  initialForm = EMPTY_FORM,
  initialOutcome = null,
  initialErrors = {},
  initialPending = false,
  initialCheckedAt = null,
  initialTab = "contract",
  validateContract = postTierI,
}: BridgeContractStudioProps) {
  const [form, setForm] = useState<ContractForm>(initialForm);
  const [errors, setErrors] = useState<FieldErrors>(initialErrors);
  const [submitted, setSubmitted] = useState(Object.keys(initialErrors).length > 0);
  const [pending, setPending] = useState(initialPending);
  const [outcome, setOutcome] = useState<Outcome | null>(initialOutcome);
  const [checkedForm, setCheckedForm] = useState<ContractForm | null>(initialOutcome ? initialForm : null);
  const [checkedAt, setCheckedAt] = useState<Date | null>(initialOutcome ? initialCheckedAt ?? new Date() : null);
  const [tab, setTab] = useState<string>(initialTab);
  const [copied, setCopied] = useState(false);
  const [flash, setFlash] = useState<FieldKey | null>(null);
  const fieldRefs = useRef<Partial<Record<FieldKey, HTMLElement | null>>>({});
  const sheetRef = useRef<HTMLElement | null>(null);
  const formRef = useRef<HTMLFormElement | null>(null);
  const uid = useId();
  const ids = {
    form: `${uid}-form`,
    odoo: `${uid}-odoo`,
    third: `${uid}-third`,
    direction: `${uid}-direction-label`,
    conflict: `${uid}-conflict-label`,
    money: `${uid}-money-label`,
  };

  const stale = Boolean(outcome && checkedForm && !formsEqual(form, checkedForm));
  const ledger = useMemo(() => buildLedger(form, outcome, { stale, pending }), [form, outcome, stale, pending]);
  const summary = ledgerSummary(ledger);
  const chip = statusChip(outcome, { stale, pending });
  const risk = overwriteRisk(form);
  const preview = useMemo(() => previewJson(form), [form]);
  const pristine = formsEqual(form, EMPTY_FORM) && !outcome && !Object.keys(errors).length;
  const fresh = outcome && !stale && !pending ? outcome : null;

  useEffect(() => {
    if (!flash) return;
    const t = window.setTimeout(() => setFlash(null), 700);
    return () => window.clearTimeout(t);
  }, [flash]);

  function update<K extends keyof ContractForm>(key: K, value: ContractForm[K]) {
    const next = { ...form, [key]: value };
    setForm(next);
    if (submitted) setErrors(validateForm(next));
  }

  const focusField = useCallback((key: FieldKey | null) => {
    if (!key) return;
    setTab("contract");
    // Tab panel may mount on this frame; focus after paint.
    window.requestAnimationFrame(() => {
      const el = fieldRefs.current[key];
      if (el) {
        el.focus();
        setFlash(key);
      }
    });
  }, []);

  async function runValidate() {
    if (pending) return;
    setSubmitted(true);
    const clientErrors = validateForm(form);
    setErrors(clientErrors);
    if (Object.keys(clientErrors).length) {
      focusField(firstErrorField(clientErrors));
      return;
    }
    setPending(true);
    const sent = form;
    try {
      const { status, body } = await validateContract(buildContract(sent));
      if (!body) {
        setOutcome({ kind: "error", guide: networkErrorGuide(status) });
      } else {
        const next = classifyResult(body);
        setOutcome(next);
        if (next.kind === "refused" && next.field && next.fieldMessage) {
          setErrors((prev) => ({ ...prev, [next.field as FieldKey]: next.fieldMessage }));
          focusField(next.field);
        }
      }
    } catch {
      setOutcome({ kind: "error", guide: networkErrorGuide() });
    } finally {
      setCheckedForm(sent);
      setCheckedAt(new Date());
      setPending(false);
      if (typeof window !== "undefined" && window.matchMedia?.("(max-width: 1023px)").matches) {
        sheetRef.current?.querySelector(".br-verdict")?.scrollIntoView({ block: "nearest" });
      }
    }
  }

  function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    void runValidate();
  }

  // Cmd/Ctrl + Enter validates from anywhere on the screen. Not animated.
  const runRef = useRef(runValidate);
  runRef.current = runValidate;
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        void runRef.current();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function onReset() {
    setForm(EMPTY_FORM);
    setErrors({});
    setSubmitted(false);
    setOutcome(null);
    setCheckedForm(null);
    setCheckedAt(null);
  }

  async function copyJson() {
    try {
      await navigator.clipboard.writeText(preview);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch {
      setCopied(false);
    }
  }

  const describe = (key: FieldKey, hintId?: string) =>
    [hintId, errors[key] ? `${uid}-${key}-error` : undefined].filter(Boolean).join(" ") || undefined;

  const fieldError = (key: FieldKey) =>
    errors[key] ? (
      <p className="br-field-error" id={`${uid}-${key}-error`} data-testid={`bridge-error-${key}`}>
        {sanitizeCopy(errors[key] as string)}
      </p>
    ) : null;

  const dirHint = DIRECTION_OPTIONS.find((o) => o.value === form.direction)?.hint ?? "";
  const conflictHint = POLICY_OPTIONS.find((o) => o.value === form.conflict)?.hint;
  const moneyHint = POLICY_OPTIONS.find((o) => o.value === form.moneyPolicy)?.hint;
  const policySegments = POLICY_OPTIONS.map((o) => ({ value: o.value, label: o.label }));

  const verdictKind = pending ? "pending" : fresh ? fresh.kind : "idle";
  const localFails = ledger.filter((r) => r.source === "local" && r.status === "fail").length;

  const endpoint = (side: "odoo" | "third", value: string, label: string, key: FieldKey) => (
    <div className="br-node" data-side={side} data-empty={value.trim() ? undefined : ""}>
      <span className="br-node-kicker">{label}</span>
      {value.trim() ? (
        <button
          type="button"
          className="br-node-id"
          onClick={() => focusField(key)}
          title={`Edit ${label} connection id`}
          data-testid={`bridge-node-${side}`}
        >
          <span translate="no">{value.trim()}</span>
        </button>
      ) : (
        <button type="button" className="br-node-add" onClick={() => focusField(key)} data-testid={`bridge-node-${side}`}>
          Set connection id
        </button>
      )}
    </div>
  );

  const contractPanel = (
    <form
      id={ids.form}
      ref={formRef}
      className="br-insp-form"
      noValidate
      onSubmit={onSubmit}
      aria-busy={pending}
      aria-label="Contract settings"
    >
      <section className="br-insp-sec">
        <h3 className="br-insp-title">Connections</h3>
        <div className="br-field" data-invalid={errors.odooId ? "" : undefined} data-flash={flash === "odooId" ? "" : undefined}>
          <label htmlFor={ids.odoo}>Odoo</label>
          <input
            id={ids.odoo}
            ref={(el) => {
              fieldRefs.current.odooId = el;
            }}
            className="br-control br-mono"
            value={form.odooId}
            onChange={(e) => update("odooId", e.target.value)}
            autoComplete="off"
            spellCheck={false}
            placeholder="odoo-main…"
            aria-invalid={errors.odooId ? true : undefined}
            aria-describedby={describe("odooId", `${uid}-conn-hint`)}
            data-testid="bridge-odoo-id"
          />
          {fieldError("odooId")}
        </div>
        <div className="br-field" data-invalid={errors.thirdId ? "" : undefined} data-flash={flash === "thirdId" ? "" : undefined}>
          <label htmlFor={ids.third}>Third party</label>
          <input
            id={ids.third}
            ref={(el) => {
              fieldRefs.current.thirdId = el;
            }}
            className="br-control br-mono"
            value={form.thirdId}
            onChange={(e) => update("thirdId", e.target.value)}
            autoComplete="off"
            spellCheck={false}
            placeholder="shopify-store…"
            aria-invalid={errors.thirdId ? true : undefined}
            aria-describedby={describe("thirdId", `${uid}-conn-hint`)}
            data-testid="bridge-third-id"
          />
          {fieldError("thirdId")}
        </div>
        <p className="br-hint" id={`${uid}-conn-hint`}>
          Connection ids, not URLs or keys. Each needs a successful Verify.
        </p>
      </section>

      <section className="br-insp-sec">
        <h3 className="br-insp-title" id={ids.direction}>
          Direction
        </h3>
        <Segmented<Direction>
          name={`${uid}-direction`}
          label="Direction"
          labelId={ids.direction}
          value={form.direction}
          options={DIRECTION_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
          onChange={(v) => update("direction", v)}
          testIdPrefix="bridge-direction"
        />
        <p className="br-hint">{dirHint}.</p>

        {form.direction === "two_way" ? (
          <div
            className="br-field br-reveal"
            data-invalid={errors.conflict ? "" : undefined}
            data-flash={flash === "conflict" ? "" : undefined}
            data-testid="bridge-conflict-field"
          >
            <span className="br-label" id={ids.conflict}>
              Conflict rule
            </span>
            <Segmented<Policy>
              name={`${uid}-conflict`}
              label="Conflict rule"
              labelId={ids.conflict}
              value={form.conflict}
              options={policySegments}
              onChange={(v) => update("conflict", v)}
              testIdPrefix="bridge-conflict"
              invalid={Boolean(errors.conflict)}
              describedBy={describe("conflict")}
              firstRef={(el) => {
                fieldRefs.current.conflict = el;
              }}
            />
            {conflictHint ? <p className="br-hint">{conflictHint} when both sides edit one order.</p> : null}
            {fieldError("conflict")}
          </div>
        ) : null}
      </section>

      <section className="br-insp-sec">
        <h3 className="br-insp-title" id={ids.money}>
          Money
        </h3>
        <label className="br-switch-row">
          <span>
            <span className="br-switch-label">Orders carry money</span>
            <span className="br-hint">Totals, taxes, and payments travel with each order.</span>
          </span>
          <input
            type="checkbox"
            role="switch"
            className="br-switch"
            checked={form.money}
            onChange={(e) => update("money", e.target.checked)}
            aria-checked={form.money}
            data-testid="bridge-money"
          />
        </label>
        {form.money ? (
          <div className="br-field br-reveal" data-flash={flash === "moneyPolicy" ? "" : undefined}>
            <span className="br-label" id={`${uid}-money-policy`}>
              When amounts disagree
            </span>
            <Segmented<Policy>
              name={`${uid}-money-policy`}
              label="Money policy"
              labelId={`${uid}-money-policy`}
              value={form.moneyPolicy}
              options={policySegments}
              onChange={(v) => update("moneyPolicy", v)}
              testIdPrefix="bridge-money-policy"
              invalid={Boolean(errors.moneyPolicy)}
              describedBy={describe("moneyPolicy")}
              firstRef={(el) => {
                fieldRefs.current.moneyPolicy = el;
              }}
            />
            {moneyHint ? <p className="br-hint">{moneyHint}.</p> : null}
            {fieldError("moneyPolicy")}
          </div>
        ) : null}
        {risk ? (
          <p className="br-risk" data-testid="bridge-risk">
            <AlertTriangle className="size-3.5" aria-hidden />
            <span>{sanitizeCopy(risk)}</span>
          </p>
        ) : null}
      </section>

      <div className="br-insp-foot">
        <Button type="button" variant="ghost" size="sm" onClick={onReset} disabled={pending || pristine} data-testid="bridge-reset-btn">
          {RESET_CTA}
        </Button>
      </div>
    </form>
  );

  const requestPanel = (
    <div className="br-insp-form">
      <section className="br-insp-sec">
        <div className="br-req-head">
          <h3 className="br-insp-title">POST /api/bridge/contracts/validate</h3>
          <Button type="button" variant="ghost" size="sm" onClick={() => void copyJson()} data-testid="bridge-copy-btn">
            {copied ? <Check className="size-3.5" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
            {copied ? "Copied" : "Copy"}
          </Button>
        </div>
        <pre className="br-code" data-testid="bridge-preview" tabIndex={0} aria-label="Request body JSON">
          <code translate="no">{preview}</code>
        </pre>
        <p className="br-hint">The exact body Tier I receives. Ids only, never secrets.</p>
      </section>
      <section className="br-insp-sec">
        <h3 className="br-insp-title">Set by Tier I</h3>
        <dl className="br-kv" data-testid="bridge-fixed-rules">
          <div>
            <dt>Webhook signature</dt>
            <dd>
              <Lock className="size-3.5" aria-hidden /> Required
            </dd>
          </div>
          <div>
            <dt>Idempotency field</dt>
            <dd className="br-mono" translate="no">
              {IDEMPOTENCY_FIELD}
            </dd>
          </div>
        </dl>
      </section>
    </div>
  );

  const verdict = (() => {
    if (pending) {
      return (
        <div className="br-verdict" data-kind="pending" data-testid="bridge-result-pending">
          <p className="br-verdict-title">
            <span className="br-dot br-dot-pulse" aria-hidden />
            Checking with Tier I…
          </p>
          <p className="br-verdict-why">Reading the contract and both connection records.</p>
        </div>
      );
    }
    if (fresh) {
      const g = fresh.guide;
      const tid = `bridge-result-${fresh.kind}`;
      return (
        <div className="br-verdict" data-kind={fresh.kind} data-testid={tid}>
          <div className="br-verdict-row">
            <p className="br-verdict-title" data-testid={`${tid}-title`}>
              <span className="br-dot" aria-hidden />
              {sanitizeCopy(g.title)}
            </p>
            {checkedAt ? (
              <time className="br-verdict-time" dateTime={checkedAt.toISOString()}>
                {TIME_FMT.format(checkedAt)}
              </time>
            ) : null}
          </div>
          <p className="br-verdict-why" data-testid={`${tid}-why`}>
            {sanitizeCopy(g.why)}
          </p>
          <p className="br-verdict-next" data-testid={`${tid}-next`}>
            <span className="br-verdict-label">Next</span> {sanitizeCopy(g.next)}
          </p>
          {fresh.kind === "error" ? (
            <div>
              <Button type="button" variant="secondary" size="sm" onClick={() => void runValidate()} data-testid="bridge-retry-btn">
                Try again
              </Button>
            </div>
          ) : null}
        </div>
      );
    }
    return (
      <div className="br-verdict" data-kind="idle" data-testid="bridge-result-idle">
        <p className="br-verdict-title">
          <span className="br-dot" aria-hidden />
          {stale ? "Edited since the last check" : localFails ? "Fix the failing rows first" : "Ready for Tier I"}
        </p>
        <p className="br-verdict-why" data-testid={stale ? "bridge-result-stale" : "bridge-result-idle-why"}>
          {stale
            ? `The ${checkedAt ? TIME_FMT.format(checkedAt) : "earlier"} result no longer matches this contract. Validate again to refresh it.`
            : "Local rows update as you type. Connection status comes from Tier I when you validate."}
        </p>
      </div>
    );
  })();

  return (
    <main className="bridge-operate" data-testid="bridge-contract-page" data-outcome={verdictKind}>
      <header className="br-bar">
        <div className="br-bar-id">
          <nav aria-label="Breadcrumb" className="br-crumbs">
            <ol>
              <li>Bridge</li>
              <li aria-hidden>/</li>
              <li>Contracts</li>
              <li aria-hidden>/</li>
              <li aria-current="page">New</li>
            </ol>
          </nav>
          <FrameMeta />
          <h1>{PAGE_TITLE}</h1>
        </div>
        <div className="br-bar-actions">
          <span className="br-chip" data-tone={chip.tone} data-testid="bridge-status-chip">
            {chip.label}
          </span>
          <p className="br-bar-honesty" data-testid="bridge-honesty">
            {HONESTY_LINE}
          </p>
          <Button
            type="submit"
            form={ids.form}
            variant="primary"
            loading={pending}
            data-testid="bridge-validate-btn"
            onClick={(e) => {
              // The form lives in the Contract tab; submit directly when the Request tab is open.
              if (!formRef.current) {
                e.preventDefault();
                void runValidate();
              }
            }}
          >
            {pending ? PRIMARY_CTA_BUSY : PRIMARY_CTA}
            <kbd className="br-kbd" aria-hidden>
              ⌘↵
            </kbd>
          </Button>
        </div>
      </header>

      <div className="br-body">
        <section className="br-canvas" aria-label="Contract sheet">
          <article className="br-sheet" ref={sheetRef} data-testid="bridge-sheet">
            <header className="br-sheet-head">
              <div>
                <h2>Orders contract</h2>
                <p>
                  One entity, <span className="br-mono" translate="no">{ENTITY_NAME}</span>, between one Odoo connection and one
                  third-party connection.
                </p>
              </div>
              <p className="br-tally" data-testid="bridge-tally">
                <span className="br-tally-n">
                  {summary.passed}/{summary.applicable}
                </span>
                <span>checks pass</span>
              </p>
            </header>

            <div className="br-flow" data-direction={form.direction} data-testid="bridge-flow">
              {endpoint("odoo", form.odooId, "Odoo", "odooId")}
              <div className="br-wire" aria-label={`Orders move ${directionLabel(form.direction)}`} role="img">
                <span className="br-wire-line" aria-hidden />
                <span className="br-wire-tag">
                  {form.direction !== "outbound" ? <ChevronRight className="br-wire-chev br-flip size-3.5" aria-hidden /> : null}
                  {DIRECTION_OPTIONS.find((o) => o.value === form.direction)?.label}
                  {form.direction !== "inbound" ? <ChevronRight className="br-wire-chev size-3.5" aria-hidden /> : null}
                </span>
              </div>
              {endpoint("third", form.thirdId, "Third party", "thirdId")}
            </div>

            <dl className="br-terms" data-testid="bridge-terms">
              <div>
                <dt>Direction</dt>
                <dd>{dirHint}</dd>
              </div>
              <div>
                <dt>Conflict rule</dt>
                <dd data-missing={form.direction === "two_way" && !form.conflict ? "" : undefined}>
                  {form.direction !== "two_way"
                    ? "Not needed one way"
                    : form.conflict
                      ? POLICY_OPTIONS.find((o) => o.value === form.conflict)?.label
                      : "Required for two-way"}
                </dd>
              </div>
              <div>
                <dt>Money</dt>
                <dd>{form.money ? `Carried. ${POLICY_OPTIONS.find((o) => o.value === form.moneyPolicy)?.label} on disagreement` : "Not carried"}</dd>
              </div>
              <div>
                <dt>Webhook signature</dt>
                <dd>
                  <Lock className="size-3.5" aria-hidden /> Required
                </dd>
              </div>
            </dl>

            <section className="br-ledger" aria-labelledby={`${uid}-ledger`}>
              <h3 id={`${uid}-ledger`}>Tier I checks</h3>
              <ul data-testid="bridge-ledger">
                {ledger.map((row) => (
                  <li key={row.id} data-status={row.status} data-testid={`bridge-check-${row.id}`}>
                    <CheckGlyph status={row.status} />
                    <span className="br-ledger-label">
                      {row.label}
                      <span className="sr-only">: {STATUS_WORD[row.status]}</span>
                    </span>
                    <span className="br-ledger-detail">{row.detail}</span>
                    <span className="br-ledger-src">{row.source === "tier" ? "Server" : "Local"}</span>
                  </li>
                ))}
              </ul>
            </section>

            <div aria-live="polite" data-testid="bridge-result" data-kind={verdictKind}>
              {verdict}
            </div>
          </article>
        </section>

        <aside className="br-inspector" aria-label="Inspector">
          <Tabs
            value={tab}
            onValueChange={setTab}
            className="br-tabs"
            items={[
              { value: "contract", label: "Contract", content: contractPanel },
              { value: "request", label: "Request", content: requestPanel },
            ]}
          />
        </aside>
      </div>
    </main>
  );
}
