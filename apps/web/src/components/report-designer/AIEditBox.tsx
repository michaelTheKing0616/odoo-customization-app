"use client";

import { ProvenanceChip } from "@/components/ui/craft";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import type { AIBlockOp, AIEditOut, Placement } from "@/lib/api/view-engine-2b";
import { Note } from "../view-designer/Note";
import styles from "./ReportDesigner.module.css";

type Props = {
  placements: Placement[];
  onPlacements: (p: Placement[]) => void;
  /** Blocks the accepted AI change added or edited, so the preview can mark them. */
  onChanged?: (marks: AIMark[], placements: Placement[]) => void;
  propose: (text: string, placements: Placement[]) => Promise<AIEditOut>;
  apply: (placements: Placement[], ops: AIBlockOp[]) => Promise<{ placements: Placement[] }>;
  what: "report" | "email";
};

/** Edit with AI: a sentence becomes a checked draft on the canvas. Nothing is published from here. */
export type AIMark = { slot: string; index: number };

/** Blocks in `after` that weren't in `before` (same slot, same content). */
export function changedBlocks(before: Placement[], after: Placement[]): AIMark[] {
  const old = new Map<string, number>();
  for (const p of before) for (const b of p.blocks) { const k = `${p.slot}|${JSON.stringify(b)}`; old.set(k, (old.get(k) ?? 0) + 1); }
  const out: AIMark[] = [];
  for (const p of after) p.blocks.forEach((b, index) => {
    const k = `${p.slot}|${JSON.stringify(b)}`;
    const n = old.get(k) ?? 0;
    if (n > 0) old.set(k, n - 1); else out.push({ slot: p.slot, index });
  });
  return out;
}

export function AIEditBox({ placements, onPlacements, onChanged, propose, apply, what }: Props) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [prop, setProp] = useState<AIEditOut | null>(null);
  const [skip, setSkip] = useState<Set<number>>(new Set());
  const [before, setBefore] = useState<Placement[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function ask(t = text) {
    if (!t.trim()) return;
    setBusy(true); setError(null);
    try { setProp(await propose(t.trim(), placements)); setSkip(new Set()); } catch (e) { setError(e instanceof Error ? e.message : "The assistant didn't answer."); } finally { setBusy(false); }
  }
  async function accept() {
    if (!prop) return;
    setBusy(true); setError(null);
    try {
      const out = await apply(placements, prop.ops.filter((_, i) => !skip.has(i)));
      setBefore(placements); onPlacements(out.placements); onChanged?.(changedBlocks(placements, out.placements), out.placements); setProp(null); setText("");
    } catch (e) { setError(e instanceof Error ? e.message : "That change can't be made safely."); } finally { setBusy(false); }
  }
  return (
    <section className={styles.panel} aria-label="Edit with AI" data-testid="ai-edit">
      <label>Describe a change to this {what}
        <Input value={text} onChange={(e) => setText(e.target.value)} placeholder="Put the customer reference under the address" maxLength={500}
          onKeyDown={(e) => { if (e.key === "Enter") void ask(); }} />
      </label>
      <div className={styles.row}>
        <Button size="sm" loading={busy && !prop} disabled={!text.trim()} onClick={() => void ask()}>Propose a change</Button>
        {before ? <Button size="sm" variant="ghost" onClick={() => { onPlacements(before); setBefore(null); }} data-testid="ai-undo">Undo the AI change</Button> : null}
      </div>
      {error ? <Note tone="danger" role="alert">{error}</Note> : null}
      {prop ? (
        prop.ops.length ? (
          <div className="ai-draft rounded-md p-2">
            <p><ProvenanceChip by="AI" /> It lands as a draft; publishing still runs the usual checks.</p>
            <ul className={styles.list}>
              {prop.descriptions.map((d, i) => (
                <li key={`${d}-${i}`}><label><input type="checkbox" checked={!skip.has(i)} onChange={() => setSkip((s) => { const n = new Set(s); if (n.has(i)) n.delete(i); else n.add(i); return n; })} /> {d}</label></li>
              ))}
            </ul>
            <div className={styles.row}>
              <Button size="sm" variant="primary" loading={busy} disabled={skip.size === prop.ops.length} onClick={() => void accept()} data-testid="ai-accept">
                {skip.size ? `Put ${prop.ops.length - skip.size} of ${prop.ops.length} in the draft` : "Put in the draft"}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setProp(null)}>Discard</Button>
            </div>
          </div>
        ) : (
          <div>
            <Note tone="info">{prop.unclear ?? "Nothing to change for that."}</Note>
            {prop.choices.length ? (
              <div className={styles.row} role="group" aria-label="Did you mean">
                {prop.choices.map((c) => <Button key={c} size="sm" variant="secondary" onClick={() => { setText(c); void ask(c); }}>{c}</Button>)}
              </div>
            ) : null}
          </div>
        )
      ) : null}
    </section>
  );
}
