"use client";

import { useEffect, useRef, useState } from "react";
import {
  PLAN_STATUS_META,
  environmentLabel,
  expiryAbsolute,
  expiryPhrase,
  riskMeaning,
  sanitizePlanInboxCopy,
  type InboxPlanCard,
  type PlanDisplayStatus,
} from "@/lib/planInboxScreen";

type PlanPaperProps = {
  plan: InboxPlanCard;
  status: PlanDisplayStatus;
  now: Date;
  timeZone?: string;
};

/** Identifier-shaped engine lines (op names, postconditions, hashes) read better in mono. */
function isTechnicalLine(line: string): boolean {
  return /^[a-z0-9_]+[.:][\w.:%/()-]*(\s|$)/i.test(line.trim()) || /^[0-9a-f]{12,}$/i.test(line.trim());
}

const KV_LINE = /^([a-z][a-z_]*)\s+(\S.*)$/;

/**
 * Engine sections that are only `key value` lines (risk, impact) read as a small
 * ledger. Text is unchanged; only the layout differs. Mixed sections stay as prose.
 */
function kvPairs(lines: string[]): Array<[string, string]> | null {
  const filled = lines.map((line) => line.trim()).filter(Boolean);
  if (filled.length === 0) return null;
  const pairs: Array<[string, string]> = [];
  for (const line of filled) {
    const match = KV_LINE.exec(line);
    if (!match) return null;
    pairs.push([match[1], match[2]]);
  }
  return pairs;
}

function opsParams(params: Record<string, unknown> | undefined): string {
  if (!params || Object.keys(params).length === 0) return "{}";
  try {
    return JSON.stringify(params, null, 2);
  } catch {
    return "{}";
  }
}

/**
 * The plan card as a document. Section titles and bodies are the engine's strings,
 * split on line breaks only, in the engine's order.
 */
export function PlanPaper({ plan, status, now, timeZone }: PlanPaperProps) {
  const meta = PLAN_STATUS_META[status];
  const sections = plan.sections ?? [];
  const changes = plan.changes ?? [];
  const absolute = expiryAbsolute(plan, { timeZone });
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  async function copyFingerprint() {
    try {
      await navigator.clipboard?.writeText(plan.plan_hash);
      setCopied(true);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }

  return (
    <article
      className="pi-paper"
      data-testid="plan-card"
      data-status={status}
      data-risk={plan.max_risk}
      aria-labelledby="pi-card-title"
    >
      <header className="pi-paper-head">
        <div className="pi-paper-kicker">
          <span className="pi-risk" data-risk={plan.max_risk} data-testid="plan-card-risk">
            {plan.max_risk}
          </span>
          <span className="pi-paper-kicker-text">{riskMeaning(plan.max_risk)}</span>
          <span className="pi-env" data-env={(plan.environment || "").toLowerCase()} data-testid="plan-card-env">
            {environmentLabel(plan.environment)}
          </span>
          <span className="pi-status" data-tone={meta.tone} data-testid="plan-card-status">
            {meta.label}
          </span>
        </div>
        <h2 id="pi-card-title" className="pi-paper-title" tabIndex={-1}>
          {plan.goal}
        </h2>
        <dl className="pi-paper-meta">
          <div className="pi-stamp">
            <dt>Fingerprint</dt>
            <dd>
              <button
                type="button"
                className="pi-stamp-btn"
                onClick={() => void copyFingerprint()}
                aria-label={`Copy fingerprint ${plan.plan_hash}`}
                data-testid="plan-card-fingerprint"
              >
                <code translate="no">{plan.plan_hash}</code>
                <span className="pi-stamp-hint" aria-hidden>
                  {copied ? "Copied" : "Copy"}
                </span>
              </button>
              <span className="sr-only" role="status">
                {copied ? "Fingerprint copied" : ""}
              </span>
            </dd>
          </div>
          <div>
            <dt>Expiry</dt>
            <dd data-testid="plan-card-expiry">
              {expiryPhrase(plan, now)}
              {absolute ? (
                <time className="pi-paper-meta-sub" dateTime={plan.expires_at}>
                  {absolute}
                </time>
              ) : null}
            </dd>
          </div>
          {plan.requester_id ? (
            <div>
              <dt>Requested by</dt>
              <dd className="pi-mono" translate="no">
                {plan.requester_id}
              </dd>
            </div>
          ) : null}
          <div>
            <dt>Ops</dt>
            <dd className="pi-num">{changes.length}</dd>
          </div>
        </dl>
      </header>

      {sections.length > 0 ? (
        <ol className="pi-doc" aria-label="Plan card sections from the engine">
          {sections.map((section, index) => {
            const lines = (section.body || "").split("\n");
            const pairs = kvPairs(lines);
            return (
              <li key={`${index}-${section.title}`} className="pi-doc-item">
                <section data-testid="plan-card-section" className="pi-doc-section">
                  <span className="pi-doc-index" aria-hidden>
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <h3 className="pi-doc-title">{section.title}</h3>
                  {pairs ? (
                    <dl className="pi-doc-body pi-doc-kv">
                      {pairs.map(([key, value], i) => (
                        <div key={`${i}-${key}`} className="pi-doc-kv-row">
                          <dt translate="no">{key}</dt>{" "}
                          <dd>{value}</dd>
                        </div>
                      ))}
                    </dl>
                  ) : (
                    <p className="pi-doc-body">
                      {lines.map((line, i) => (
                        <span key={i} className="pi-doc-line" data-technical={isTechnicalLine(line) ? "true" : undefined}>
                          {line}
                          {i < lines.length - 1 ? "\n" : null}
                        </span>
                      ))}
                    </p>
                  )}
                </section>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="pi-paper-empty" data-testid="plan-card-no-sections">
          The engine sent no sections for this card. Refresh the inbox before deciding.
        </p>
      )}

      {changes.length > 0 ? (
        <details className="pi-ops" data-testid="plan-card-ops">
          <summary>
            <span>Exact ops this fingerprint covers</span>
            <span className="pi-num pi-ops-count">{changes.length}</span>
          </summary>
          <ol className="pi-ops-list">
            {changes.map((change, index) => (
              <li key={index} className="pi-ops-item">
                <p className="pi-ops-desc">{sanitizePlanInboxCopy(change.description || `Op ${index + 1}`)}</p>
                <pre className="pi-ops-pre" translate="no">
                  {opsParams(change.params)}
                </pre>
              </li>
            ))}
          </ol>
        </details>
      ) : null}
    </article>
  );
}
