"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import type { Condition, EngineViewType } from "@/lib/api/view-engine";
import type { DepsOut, RequiredImpactOut, TourStep } from "@/lib/api/view-engine-2c";
import { Note } from "../view-designer/Note";
import styles from "./ViewDesigner.module.css";

/** Before hiding or removing a field: everything else in this database that uses it. */
export function FieldDepsPanel(p: {
  connectionId: string;
  model: string;
  viewType: EngineViewType;
  viewId: number | null;
  field: string;
  onJump: (nodeId: string) => void;
  errorText: (err: unknown) => string;
}) {
  const [out, setOut] = useState<DepsOut | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setOut(null);
    setError(null);
  }, [p.field, p.model]);
  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      setOut(await api.fieldDeps(p.connectionId, { model: p.model, view_type: p.viewType, view_id: p.viewId }, p.field));
    } catch (err) {
      setError(p.errorText(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className={styles.stack} data-testid="vd-deps">
      <h3 className={styles.sectionTitle}>Where this field is used</h3>
      {!out ? (
        <Button size="sm" variant="ghost" loading={busy} onClick={() => void run()}>Check before hiding or removing</Button>
      ) : (
        <>
          <p data-level={out.level} className={out.level === "blocked" ? styles.block2 : out.level === "safe" ? styles.ok : undefined} role="status">
            {out.verdict}
          </p>
          <ul className={styles.list}>
            {out.groups.map((g) => (
              <li key={g.kind}>
                <details>
                  <summary>
                    {g.title} ({g.count}){g.risk === "high" ? <span className={styles.muted}>, important</span> : null}
                  </summary>
                  <ul className={styles.list}>
                    {g.items.map((it, i) => (
                      <li key={`${g.kind}-${i}`} className={styles.listItem}>
                        <span>
                          {it.name} <span className={styles.muted}>{it.detail}</span>
                        </span>
                        {it.node ? <Button size="sm" variant="ghost" onClick={() => p.onJump(it.node!)}>Show</Button> : null}
                      </li>
                    ))}
                  </ul>
                </details>
              </li>
            ))}
          </ul>
        </>
      )}
      {error ? <Note tone="danger" role="alert">{error}</Note> : null}
    </section>
  );
}

/** Under a "required when ..." rule: how many records that rule affects today. */
export function RequiredImpact(p: {
  connectionId: string;
  model: string;
  field: string;
  condition: Condition | null;
  inverted?: boolean;
  errorText: (err: unknown) => string;
}) {
  const [out, setOut] = useState<RequiredImpactOut | null>(null);
  const key = JSON.stringify(p.condition);
  useEffect(() => {
    if (p.inverted) return;
    let live = true;
    setOut(null);
    const t = window.setTimeout(() => {
      api
        .requiredImpact(p.connectionId, p.model, p.field, p.condition)
        .then((o) => live && setOut(o))
        .catch((err) => live && setOut({ countable: false, text: p.errorText(err) }));
    }, 300);
    return () => {
      live = false;
      window.clearTimeout(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.connectionId, p.model, p.field, key, p.inverted]);
  if (p.inverted) return <p className={styles.muted}>Counts are shown for &quot;required when&quot; rules.</p>;
  if (!out) return <Note tone="busy" role="status">Counting records…</Note>;
  return (
    <p className={out.countable && out.missing ? styles.flag : styles.muted} data-testid="vd-required-impact" role="status">
      {out.text}
    </p>
  );
}

/** SVG colour filters used by the vision simulation (Machado et al. 2009 matrices, severity 1). */
export function VisionFilters() {
  return (
    <svg width="0" height="0" aria-hidden focusable="false" className={styles.svgDefs}>
      <filter id="vd-protanopia"><feColorMatrix type="matrix" values="0.152 1.053 -0.205 0 0  0.115 0.786 0.099 0 0  -0.004 -0.048 1.052 0 0  0 0 0 1 0" /></filter>
      <filter id="vd-deuteranopia"><feColorMatrix type="matrix" values="0.367 0.861 -0.228 0 0  0.280 0.673 0.047 0 0  -0.012 0.043 0.969 0 0  0 0 0 1 0" /></filter>
      <filter id="vd-tritanopia"><feColorMatrix type="matrix" values="1.256 -0.077 -0.179 0 0  -0.078 0.931 0.148 0 0  0.005 0.691 0.304 0 0  0 0 0 1 0" /></filter>
    </svg>
  );
}

/** The guided tour card: one step at a time, the canvas outlines the item it talks about. */
export function TourCard(p: { steps: TourStep[]; at: number; onAt: (n: number) => void; onEnd: () => void }) {
  const step = p.steps[Math.min(p.at, p.steps.length - 1)];
  if (!step) return null;
  return (
    <div className={styles.tour} role="dialog" aria-label="Screen tour" data-testid="vd2c-tour">
      <strong>{step.title}</strong>
      <p>{step.text}</p>
      <div className={styles.row}>
        <span className={styles.muted}>{p.at + 1} of {p.steps.length}</span>
        <Button size="sm" variant="ghost" disabled={p.at === 0} onClick={() => p.onAt(p.at - 1)}>Back</Button>
        {p.at < p.steps.length - 1 ? (
          <Button size="sm" variant="primary" onClick={() => p.onAt(p.at + 1)}>Next</Button>
        ) : null}
        <Button size="sm" variant="ghost" onClick={p.onEnd}>End tour</Button>
      </div>
    </div>
  );
}
