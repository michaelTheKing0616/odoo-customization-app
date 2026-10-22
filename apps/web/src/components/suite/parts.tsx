"use client";
import { Spokes } from "@/components/loading-ui/spokes";

import type { ReactNode } from "react";
import { AlertTriangle, Check, CircleAlert, IconAccess as Shield, IconUndo as Undo, Info, Lock } from "@/components/ui/icons";
import type { RunStepState, Verdict } from "@/lib/api/suite";
import { useSuite } from "./SuiteContext";
import styles from "./Suite.module.css";
import { FrameMeta } from "@/components/frame/FrameMeta";

/** Shared suite parts (spec 5), structure first. Status is always icon + words, never colour only. */
export function PageHead({ title, purpose, actions }: { title: string; purpose: string; actions?: ReactNode }) {
  return (
    <div className={`${styles.head} studio-bar-dark`}>
      <div className={styles.grow}>
        <FrameMeta />
        <h1>{title}</h1>
        <p>{purpose}</p>
      </div>
      {actions}
    </div>
  );
}

type Tone = "info" | "success" | "warning" | "danger" | "busy";
const TONE_ICON = { info: Info, success: Check, warning: AlertTriangle, danger: CircleAlert, busy: Spokes } as const;

export function Status({ tone = "info", children, ...rest }: { tone?: Tone; children: ReactNode } & Record<string, unknown>) {
  const Icon = TONE_ICON[tone];
  return (
    <p className={styles.status} data-tone={tone} role={tone === "danger" ? "alert" : tone === "busy" || tone === "success" ? "status" : undefined} {...rest}>
      <Icon aria-hidden />
      <span>{children}</span>
    </p>
  );
}

export const VERDICT_WORD: Record<Verdict, string> = {
  ready: "Ready", no_change: "Nothing to change", needs_input: "Needs input", blocked: "Blocked", waiting: "Waiting",
};
export const STATE_WORD: Record<RunStepState, string> = {
  waiting: "Waiting", running: "Running", done: "Done", failed: "Failed", skipped: "Skipped", no_change: "Nothing to change",
};
const VERDICT_ICON: Record<Verdict, React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>> = { ready: Check, no_change: Check, needs_input: AlertTriangle, blocked: CircleAlert, waiting: Spokes };
const STATE_ICON: Record<RunStepState, React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>> = { waiting: Spokes, running: Spokes, done: Check, failed: CircleAlert, skipped: Info, no_change: Check };

export function VerdictIcon({ verdict }: { verdict: Verdict }) {
  const I = VERDICT_ICON[verdict];
  return <I aria-hidden />;
}
export function StateIcon({ state }: { state: RunStepState }) {
  const I = STATE_ICON[state];
  return <I aria-hidden />;
}

/** Safety level (spec 7): one of four plain levels. */
export type Level = "look" | "undo" | "hard" | "never";
const LEVEL: Record<Level, { word: string; icon: typeof Check }> = {
  look: { word: "Look only", icon: Info },
  undo: { word: "Undo available", icon: Undo },
  hard: { word: "Hard to undo", icon: AlertTriangle },
  never: { word: "Never here", icon: Lock },
};
export function SafetyLevel({ level }: { level: Level }) {
  const L = LEVEL[level];
  return <span className={styles.tag} data-level={level}><L.icon aria-hidden width={12} height={12} /> {L.word}</span>;
}
export function levelOf(reversibility: "one_way" | "revert" | "remove", risk: string): Level {
  if (risk === "guarded" && reversibility === "one_way") return "hard";
  return reversibility === "one_way" ? "hard" : "undo";
}

export function PassportCard() {
  const { home, readAt } = useSuite();
  if (!home) return null;
  const p = home.passport;
  const ed = p.edition === "enterprise" ? "Enterprise" : p.edition === "community" ? "Community" : "edition unknown";
  const host = { online: "Odoo Online", sh: "Odoo.sh", onprem: "Self-hosted", unknown: "hosting unknown" }[p.hosting] ?? p.hosting;
  return (
    <section className={styles.card} aria-label="Instance passport" data-testid="suite-passport">
      <p className={styles.flush}><strong>{p.database}</strong> · Odoo <span data-testid="suite-version">{p.version}</span> {ed} · {host}</p>
      <p className={styles.mutedLine}>
        {p.apps.length} apps · {p.companies.length} {p.companies.length === 1 ? "company" : "companies"} · {p.languages.length} {p.languages.length === 1 ? "language" : "languages"}
      </p>
      <p className={styles.mutedLine}>
        Localization: {p.companies[0]?.country || "not set"}{p.localization.length ? ` (${p.localization.join(", ")})` : ""} · <Shield aria-hidden width={12} height={12} /> Money guard on
      </p>
      {readAt ? <p className={styles.mutedLine}>Read from the database at {readAt.toLocaleTimeString()}. The version belongs to the database, so there is nothing to switch.</p> : null}
    </section>
  );
}


/** Local time for a UTC timestamp, for the people reading it. */
export function fmtWhen(iso?: string | null): string {
  if (!iso) return "soon";
  return `on ${new Date(iso).toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZoneName: "short" })}`;
}
