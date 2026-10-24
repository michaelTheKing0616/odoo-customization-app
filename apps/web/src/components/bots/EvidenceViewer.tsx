"use client";

/**
 * BV-UI: evidence for one verify run, shown in the Bots area.
 * Types only from botVerify.ts; the parent loads the run and passes artifactUrl.
 */
import * as React from "react";
import type { CheckResult, Layer, LayerResult, LayerStatus, RunStatus, VerifyRun, WalkStep } from "@/lib/api/botVerify";
import { Callout } from "@/components/ui/Callout";
import { Card, EmptyState, Kbd, Skeleton } from "@/components/ui/layout-primitives";
import { TechName } from "@/components/ui/TechName";
import { AlertTriangle, Check, CircleAlert, Info, Loader2, X } from "@/components/ui/icons";
import { usePrefersReducedMotion } from "@/components/ui/motion/usePrefersReducedMotion";
import { cn } from "@/lib/cn";

export type EvidenceViewerProps = {
  run: VerifyRun | null;
  artifactUrl: (screenshotId: string) => string;
  loading?: boolean;
  /** True when the run could not be loaded. */
  error?: boolean;
  /** Plain-language explanation from the parent (what happened and why); never a raw error. */
  errorCopy?: string;
  onRetry?: () => void;
  denied?: { group: string } | null;
  onStart?: () => void;
};

type ViewState = "ready" | "loading" | "empty" | "partial" | "error" | "denied";
type Tone = "success" | "danger" | "warning" | "neutral";

const RUN: Record<RunStatus, { label: string; tone: Tone; hint: string }> = {
  queued: { label: "Waiting to start", tone: "neutral", hint: "The check starts in a moment." },
  running: { label: "Checking now", tone: "neutral", hint: "Results appear as each part finishes." },
  passed: { label: "All checks passed", tone: "success", hint: "The change works as planned." },
  failed: { label: "A check failed", tone: "danger", hint: "See the failed step below for what went wrong." },
  needs_human: { label: "Needs a person to look", tone: "warning", hint: "Ingenium could not decide on its own. Read the notes below." },
  rolled_back: { label: "Change undone", tone: "danger", hint: "The failed step and its screenshot are below." },
};
const LAYER: Record<Layer, { title: string; what: string }> = {
  live: { title: "Read back from Odoo", what: "Each change was read back to confirm it saved." },
  walkthrough: { title: "Walked through the screens", what: "A test user opened the screens and used them." },
  flows: { title: "Ran business flows", what: "Everyday tasks ran end to end on a throwaway copy." },
};
const LAYER_STATUS: Record<LayerStatus, { label: string; tone: Tone }> = {
  passed: { label: "Passed", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
  skipped: { label: "Skipped", tone: "neutral" },
};
const ACTION: Record<WalkStep["action"], string> = { open: "Open", click: "Click", fill: "Fill in", assert: "Check" };
const NOTICE_PREFIX = "platform notice: ";
const SENSITIVE = /(key|token|secret|pass|pwd|email|phone|mobile|login|cookie|session|auth|iban|account_number|vat)/i;

const toneText: Record<Tone, string> = {
  success: "text-success-strong",
  danger: "text-danger-strong",
  warning: "text-warning-strong",
  neutral: "text-muted",
};
const toneChip: Record<Tone, string> = {
  success: "border-border-subtle bg-surface text-ink",
  danger: "border-danger/30 bg-danger-subtle text-ink",
  warning: "border-warning/30 bg-warning-subtle text-ink",
  neutral: "border-border-subtle bg-surface-muted text-ink",
};

function ToneIcon({ tone, spin }: { tone: Tone; spin?: boolean }) {
  const cls = cn("h-4 w-4 shrink-0", toneText[tone], spin && "motion-safe:animate-spin");
  if (spin) return <Loader2 className={cls} aria-hidden />;
  if (tone === "success") return <Check className={cls} aria-hidden />;
  if (tone === "danger") return <X className={cls} aria-hidden />;
  if (tone === "warning") return <AlertTriangle className={cls} aria-hidden />;
  return <Info className={cls} aria-hidden />;
}

const fmt = new Intl.DateTimeFormat("en-NG", {
  timeZone: "Africa/Lagos",
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});
const num = new Intl.NumberFormat("en-NG");
export function watTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "Unknown time";
  return `${fmt.format(d)} WAT`;
}
function duration(a: string, b: string | null): string | null {
  if (!b) return null;
  const s = Math.max(0, Math.round((new Date(b).getTime() - new Date(a).getTime()) / 1000));
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`;
}
function plain(check: string): string {
  const t = check.replace(/[_.]+/g, " ").replace(/\bacl\b/gi, "access rule").trim();
  return t.charAt(0).toUpperCase() + t.slice(1);
}
function viewState(p: EvidenceViewerProps): ViewState {
  if (p.denied) return "denied";
  if (p.error) return "error";
  if (p.loading && !p.run) return "loading";
  if (!p.run) return "empty";
  if (p.run.status === "queued" || p.run.status === "running") return "partial";
  return "ready";
}

/** Skeleton waits 300 ms, then stays at least 500 ms so it never flashes. */
function useCalmSkeleton(active: boolean): boolean {
  const [shown, setShown] = React.useState(false);
  const since = React.useRef(0);
  React.useEffect(() => {
    if (active) {
      const t = window.setTimeout(() => {
        since.current = Date.now();
        setShown(true);
      }, 300);
      return () => window.clearTimeout(t);
    }
    if (!shown) return;
    const left = Math.max(0, 500 - (Date.now() - since.current));
    const t = window.setTimeout(() => setShown(false), left);
    return () => window.clearTimeout(t);
  }, [active, shown]);
  return shown;
}

export function EvidenceViewer(props: EvidenceViewerProps) {
  const state = viewState(props);
  const skeleton = useCalmSkeleton(state === "loading");
  return (
    <section data-testid="evidence-viewer" data-state={state} aria-label="Change check evidence" className="flex flex-col gap-4">
      {state === "loading" ? (
        <Card className="p-4" aria-busy="true">
          <p className="text-ui-body text-muted" role="status">Loading the check results.</p>
          {skeleton ? (
            <div className="mt-4 grid gap-3">
              <Skeleton className="h-8 w-56" />
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-48 w-full" />
            </div>
          ) : (
            <div className="mt-4 h-[17.5rem]" aria-hidden />
          )}
        </Card>
      ) : null}
      {state === "empty" ? (
        <EmptyState
          title="No checks yet"
          description="After a change is applied, Ingenium tests it on a throwaway copy and shows the proof here."
          action={
            props.onStart ? (
              <button type="button" onClick={props.onStart} className="min-h-11 rounded-md bg-accent px-4 text-ui-body font-medium text-on-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring">
                Check this change
              </button>
            ) : undefined
          }
        />
      ) : null}
      {state === "error" ? (
        <Callout
          variant="danger"
          title="The check results did not load"
          actions={
            props.onRetry ? (
              <button type="button" onClick={props.onRetry} className="min-h-11 rounded-md border border-border-strong bg-surface px-4 text-ui-body font-medium text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring">
                Retry
              </button>
            ) : undefined
          }
        >
          <p>{props.errorCopy ?? "Ingenium could not reach the check results just now."}</p>
          <p className="mt-1">Your Odoo data was not changed. {props.onRetry ? "Try again now." : "Try again in a minute."}</p>
        </Callout>
      ) : null}
      {state === "denied" && props.denied ? (
        <Callout variant="warning" title="You can't see these results yet">
          <p>
            Viewing check results needs the <TechName name={props.denied.group} /> group. Ask a workspace admin to add it.
          </p>
        </Callout>
      ) : null}
      {props.run && (state === "ready" || state === "partial") ? <RunView run={props.run} artifactUrl={props.artifactUrl} /> : null}
    </section>
  );
}

function RunView({ run, artifactUrl }: { run: VerifyRun; artifactUrl: (id: string) => string }) {
  const s = RUN[run.status];
  const checks = run.layers.flatMap((l) => l.checks);
  const steps = run.layers.flatMap((l) => l.steps);
  const shots = steps.filter((x) => x.screenshot_id).length;
  const took = duration(run.started_at, run.finished_at);
  const working = run.status === "queued" || run.status === "running";
  const cells: [string, string, string][] = [
    ["Checks passed", `${num.format(checks.filter((c) => c.passed).length)} of ${num.format(checks.length)}`, "Read back from Odoo"],
    ["Steps passed", `${num.format(steps.filter((x) => x.passed).length)} of ${num.format(steps.length)}`, "Screens walked"],
    ["Screenshots", num.format(shots), "Personal details masked"],
    ["Parts run", `${num.format(run.layers.filter((l) => l.status !== "skipped").length)} of ${num.format(run.layers.length)}`, working ? "More to come" : "Finished"],
  ];
  return (
    <>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-ui-title font-semibold text-ink [text-wrap:balance]">Did this change work?</h2>
          <p className="tabular mt-1 text-ui-label text-muted">
            Started {watTime(run.started_at)}
            {took ? ` · took ${took}` : ""}
          </p>
        </div>
        <span
          data-testid="run-status"
          data-status={run.status}
          className={cn("inline-flex min-h-7 items-center gap-1.5 rounded-sm border px-2.5 text-ui-label font-medium", toneChip[s.tone])}
        >
          <ToneIcon tone={s.tone} spin={working} />
          {s.label}
        </span>
      </header>
      <p className="text-ui-body text-muted [text-wrap:pretty]">{s.hint}</p>

      {run.status === "rolled_back" ? (
        <div data-testid="rollback-state">
          <Callout variant="danger" title="Change undone">
            <p>A check failed, so Ingenium rolled the change back. Odoo is as it was before the change.</p>
          </Callout>
        </div>
      ) : null}

      <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-md border border-border-subtle bg-border-subtle sm:grid-cols-4">
        {cells.map(([label, value, cap]) => (
          <div key={label} className="bg-surface-raised p-3">
            <dt className="text-ui-label text-muted">{label}</dt>
            <dd className="tabular mt-1 text-2xl font-semibold tracking-[var(--tracking-title)] text-ink">{value}</dd>
            <dd className="text-ui-label text-subtle">{cap}</dd>
          </div>
        ))}
      </dl>

      <Card className="p-0">
        <h3 className="border-b border-border-subtle px-4 py-3 text-ui-title font-medium text-ink">What was checked</h3>
        <ul className="divide-y divide-border-subtle">
          {run.layers.map((l) => (
            <LayerRow key={l.layer} layer={l} />
          ))}
        </ul>
      </Card>

      {checks.length ? <ChecksTable checks={checks} /> : null}
      {steps.length ? <Timeline steps={steps} artifactUrl={artifactUrl} /> : null}
    </>
  );
}

function LayerRow({ layer }: { layer: LayerResult }) {
  const st = LAYER_STATUS[layer.status];
  const notice = layer.reason?.startsWith(NOTICE_PREFIX) ? layer.reason.slice(NOTICE_PREFIX.length) : null;
  return (
    <li data-testid={`layer-${layer.layer}`} data-status={layer.status} className="flex flex-col gap-2 px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-ui-body font-medium text-ink">{LAYER[layer.layer].title}</p>
          <p className="text-ui-label text-muted">{LAYER[layer.layer].what}</p>
        </div>
        <span className={cn("inline-flex min-h-7 items-center gap-1.5 rounded-sm border px-2 text-ui-label", toneChip[st.tone])}>
          <ToneIcon tone={st.tone} />
          {st.label}
        </span>
      </div>
      {notice ? (
        <div data-testid={`notice-${layer.layer}`} data-tone="warning">
          <Callout variant="warning" title="Needs a person to look">
            <p>{notice}</p>
            <p className="mt-1">Nothing was undone. A person should decide whether non-admin users need that access.</p>
          </Callout>
        </div>
      ) : layer.reason ? (
        <p className="text-ui-body text-muted [text-wrap:pretty]">
          <span className="font-medium text-ink">{layer.status === "skipped" ? "Why skipped: " : "What happened: "}</span>
          {layer.reason}
        </p>
      ) : null}
    </li>
  );
}

function maskValue(k: string, v: string): React.ReactNode {
  if (SENSITIVE.test(k)) return <span className="italic text-subtle">hidden</span>;
  if (/^[a-z_]+(\.[a-z0-9_]+)+$/.test(v)) return <TechName name={v} />;
  return <span className="break-words">{v}</span>;
}

function Evidence({ evidence, className }: { evidence: Record<string, string>; className?: string }) {
  const rows = Object.entries(evidence);
  if (!rows.length) return null;
  return (
    <dl data-testid="check-evidence" className={cn("grid gap-0.5", className)}>
      {rows.map(([k, v]) => (
        <div key={k} className="flex min-w-0 flex-wrap gap-1 text-ui-label">
          <dt className="text-muted">{plain(k)}:</dt>
          <dd className="min-w-0 break-all">{maskValue(k, v)}</dd>
        </div>
      ))}
    </dl>
  );
}

function ChecksTable({ checks }: { checks: CheckResult[] }) {
  return (
    <Card className="p-0">
      <h3 className="border-b border-border-subtle px-4 py-3 text-ui-title font-medium text-ink">Check results by change</h3>
      <table className="w-full text-left text-ui-body">
        <thead className="text-ui-label text-muted">
          <tr>
            <th scope="col" className="px-4 py-2 font-medium">Change</th>
            <th scope="col" className="px-4 py-2 font-medium">Check</th>
            <th scope="col" className="px-4 py-2 font-medium">Result</th>
            <th scope="col" className="hidden px-4 py-2 font-medium sm:table-cell">Details</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border-subtle">
          {checks.map((c, i) => (
            <tr key={`${c.op_index}-${c.check}-${i}`} data-testid="check-row" data-passed={String(c.passed)} className="align-top transition-colors duration-75 hover:bg-surface-muted">
              <td className="tabular px-4 py-2 text-muted">Change {num.format(c.op_index + 1)}</td>
              <td className="px-4 py-2 text-ink">
                {plain(c.check)}
                <Evidence evidence={c.evidence} className="mt-1 sm:hidden" />
              </td>
              <td className="px-4 py-2">
                <span className="inline-flex items-center gap-1.5">
                  <ToneIcon tone={c.passed ? "success" : "danger"} />
                  {c.passed ? "Passed" : "Failed"}
                </span>
              </td>
              <td className="hidden px-4 py-2 sm:table-cell">
                <Evidence evidence={c.evidence} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function Timeline({ steps, artifactUrl }: { steps: WalkStep[]; artifactUrl: (id: string) => string }) {
  const [sel, setSel] = React.useState(() => Math.max(0, steps.findIndex((s) => !s.passed)));
  const refs = React.useRef<(HTMLLIElement | null)[]>([]);
  const reduced = usePrefersReducedMotion();
  const go = (i: number) => {
    const n = Math.min(steps.length - 1, Math.max(0, i));
    setSel(n);
    refs.current[n]?.focus();
  };
  const onKey = (e: React.KeyboardEvent, i: number) => {
    const map: Record<string, number> = {
      ArrowRight: i + 1, ArrowDown: i + 1, j: i + 1,
      ArrowLeft: i - 1, ArrowUp: i - 1, k: i - 1,
      Home: 0, End: steps.length - 1,
    };
    if (e.key in map) {
      e.preventDefault();
      go(map[e.key]);
    }
  };
  const step = steps[sel];
  const label = (s: WalkStep) => `Step ${s.index + 1}: ${ACTION[s.action]} ${s.target}`;
  return (
    <Card className="p-0">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-subtle px-4 py-3">
        <h3 className="text-ui-title font-medium text-ink" id="bv-timeline-title">Screenshot timeline</h3>
        <p className="hidden text-ui-label text-muted sm:block">
          <Kbd>j</Kbd> <Kbd>k</Kbd> or arrow keys to move
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 p-4 lg:grid-cols-[minmax(0,16rem)_minmax(0,1fr)]">
        <ul role="listbox" aria-labelledby="bv-timeline-title" aria-label="Screenshot timeline" className="flex min-w-0 flex-col gap-1">
          {steps.map((s, i) => (
            <li
              key={s.index}
              ref={(el) => {
                refs.current[i] = el;
              }}
              role="option"
              aria-selected={i === sel}
              tabIndex={i === sel ? 0 : -1}
              onClick={() => go(i)}
              onKeyDown={(e) => onKey(e, i)}
              className={cn(
                "flex min-h-11 cursor-pointer items-center gap-2 rounded-md border px-3 text-ui-body focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring",
                i === sel ? "border-accent/40 bg-accent-subtle text-on-accent-subtle" : "border-transparent text-ink [@media(hover:hover)_and_(pointer:fine)]:hover:bg-surface-muted",
              )}
            >
              <span className="tabular w-5 text-ui-label text-muted">{s.index + 1}</span>
              <ToneIcon tone={s.passed ? "success" : "danger"} />
              <span className="line-clamp-2 min-w-0 flex-1 break-words py-1">
                {ACTION[s.action]} {s.target}
              </span>
              <span className="sr-only">{s.passed ? "passed" : "failed"}</span>
            </li>
          ))}
        </ul>
        <figure
          data-testid="shot-preview"
          data-motion={reduced ? "reduced" : "full"}
          key={sel}
          className={cn(
            "min-w-0 rounded-md border border-border-subtle bg-surface-muted p-2",
            reduced ? "" : "motion-safe:animate-[bv-rise_200ms_cubic-bezier(0.23,1,0.32,1)]",
          )}
        >
          {step?.screenshot_id ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={artifactUrl(step.screenshot_id)} alt={`${label(step)}, screenshot with personal details masked`} className="aspect-[16/10] w-full rounded-sm bg-surface object-contain object-top" />
          ) : (
            <div className="flex aspect-[16/10] items-center justify-center rounded-sm bg-surface text-ui-body text-muted">
              No screenshot for this step
            </div>
          )}
          {step ? (
            <figcaption className="mt-2 flex flex-wrap items-center gap-2 text-ui-body text-ink">
              {step.passed ? <ToneIcon tone="success" /> : <CircleAlert className="h-4 w-4 text-danger-strong" aria-hidden />}
              {label(step)}
              <span className="text-muted">{step.passed ? "worked" : "did not work"}</span>
              {step.op_index !== null ? <span className="tabular text-ui-label text-muted">for change {step.op_index + 1}</span> : null}
            </figcaption>
          ) : null}
        </figure>
      </div>
      <style>{"@keyframes bv-rise{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}"}</style>
    </Card>
  );
}
