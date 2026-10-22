"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { HealthArch } from "@/components/ui/craft";
import { api } from "@/lib/api";
import type { EngineOp, EngineViewType } from "@/lib/api/view-engine";
import type { ChecksOut, Finding, TidyOut } from "@/lib/api/view-engine-2b";
import { allFixOps, healthWord } from "@/lib/viewDesigner2b";
import { Note } from "../view-designer/Note";
import styles from "./ViewDesigner.module.css";

type Props = {
  connectionId: string;
  model: string;
  viewType: EngineViewType;
  viewId: number | null;
  ops: EngineOp[];
  onOps: (ops: EngineOp[], summary: string) => void;
  onJump: (nodeId: string) => void;
  errorText: (err: unknown) => string;
};

/** Health score, layout checks, usage suggestions and performance hints, each with a one-click fix. */
export function ChecksPanel({ connectionId, model, viewType, viewId, ops, onOps, onJump, errorText }: Props) {
  const [data, setData] = useState<ChecksOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [tidy, setTidy] = useState<TidyOut | null>(null);
  const [tidying, setTidying] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      // Checks include pending changes, so fixes can be seen before publishing.
      setData(await api.checks(connectionId, { model, view_type: viewType, view_id: viewId, ops }));
      setError(null);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }, [connectionId, model, viewType, viewId, ops, errorText]);

  useEffect(() => {
    const t = window.setTimeout(() => void load(), 400);
    return () => window.clearTimeout(t);
  }, [load]);

  const fix = (f: Finding) => onOps(f.ops, f.fix_label ?? "Fix");

  const list = (title: string, items: Finding[], testid: string) =>
    items.length ? (
      <section className={styles.section} aria-label={title} data-testid={testid}>
        <h3 className={styles.sectionTitle}>
          {title} ({items.length})
          {items.filter((i) => i.ops.length).length > 1 ? (
            <Button size="sm" variant="ghost" onClick={() => onOps(allFixOps(items), `Fix all: ${title.toLowerCase()}`)}>Fix all</Button>
          ) : null}
        </h3>
        <ul className={styles.fieldList}>
          {items.map((f, i) => (
            <li key={`${f.kind}-${f.node ?? i}`} className={styles.listItem}>
              <span>
                {f.node ? (
                  <button type="button" className={styles.button} onClick={() => onJump(f.node!)}>{f.text}</button>
                ) : (
                  f.text
                )}
                {f.detail ? <span className={styles.muted}> {f.detail}</span> : null}
              </span>
              {f.ops.length && f.fix_label ? (
                <Button size="sm" variant="ghost" onClick={() => fix(f)} data-testid={`vd-fix-${f.kind}`}>{f.fix_label}</Button>
              ) : null}
            </li>
          ))}
        </ul>
      </section>
    ) : null;

  return (
    <div className={styles.panelBody} data-testid="vd-checks">
      {error ? <Note tone="danger" role="alert">{error}</Note> : null}
      {loading && !data ? <Note tone="busy" role="status">Checking this screen…</Note> : null}
      {data ? (
        <>
          <section className={styles.section} aria-label="Health score">
            <HealthArch score={data.health.score} parts={data.health.parts} label="Screen health" />
            <p className={styles.panelTitle} data-testid="vd-health">
              Health {data.health.score}/100, {healthWord(data.health.score).word}
            </p>
            <ul className={styles.chipList}>
              {data.health.parts.map((p) => (
                <li key={p.key} className={styles.chip}>{p.label}: {p.score}</li>
              ))}
            </ul>
            <p className={styles.muted}>Counts only; no record contents are read. {data.total ? `${data.total.toLocaleString()} records.` : ""}</p>
          </section>
          {list("Layout checks", data.issues, "vd-issues")}
          {list("Suggestions from how it's used", data.suggestions, "vd-suggestions")}
          {list("Speed", data.performance, "vd-performance")}
          {!data.issues.length && !data.suggestions.length && !data.performance.length ? <Note tone="success">Nothing to fix.</Note> : null}
        </>
      ) : null}

      <section className={styles.section} aria-label="Tidy up">
        <h3 className={styles.sectionTitle}>Tidy up</h3>
        <p className={styles.muted}>Groups fields by meaning and puts the most used first. You see every move before anything changes.</p>
        <Button
          size="sm"
          loading={tidying}
          onClick={async () => {
            setTidying(true);
            try {
              setTidy(await api.tidy(connectionId, { model, view_type: viewType, view_id: viewId, ops }));
            } catch (err) {
              setError(errorText(err));
            } finally {
              setTidying(false);
            }
          }}
          data-testid="vd-tidy"
        >
          Suggest a tidier layout
        </Button>
        {tidy ? (
          <div className={styles.proposal} data-testid="vd-tidy-plan">
            {tidy.note ? <p className={styles.muted}>{tidy.note}</p> : null}
            {tidy.descriptions.length ? (
              <>
                <ol>{tidy.descriptions.map((d, i) => <li key={i}>{d}</li>)}</ol>
                <div className={styles.row}>
                  <Button size="sm" variant="primary" onClick={() => { onOps(tidy.ops, "Tidy up"); setTidy(null); }}>Apply these moves</Button>
                  <Button size="sm" variant="ghost" onClick={() => setTidy(null)}>Dismiss</Button>
                </div>
              </>
            ) : null}
          </div>
        ) : null}
      </section>
    </div>
  );
}
