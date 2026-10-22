"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import type { Placement } from "@/lib/api/view-engine-2b";
import { blockCount } from "@/lib/viewDesigner2b";
import styles from "./ReportDesigner.module.css";
import { noteWriteRefusal } from "../view-designer/writeModeSignal";
import { Term } from "@/components/ui/Term";

/** Saved block sets for a record type, shared by print layouts and emails. */
export function BlockSets({ connectionId, model, placements, email, onUse }: { connectionId: string; model: string; placements: Placement[]; email: boolean; onUse: (p: Placement[]) => void }) {
  const [sets, setSets] = useState<Awaited<ReturnType<typeof api.blockSetList>>["sets"] | null>(null);
  const [name, setName] = useState("");
  const load = () => api.blockSetList(connectionId, model).then((o) => setSets(o.sets)).catch(() => setSets([]));
  const shown = (sets ?? []).filter((st) => !email || st.usable_in_email);
  return (
    <div className={styles.stack} data-testid="rd-block-sets">
      <Button size="sm" variant="ghost" onClick={() => (sets ? setSets(null) : void load())}>Saved block sets…</Button>
      {sets ? (
        <>
          {shown.map((st) => (
            <div key={st.id} className={styles.inline}>
              <Button size="sm" variant="ghost" onClick={() => onUse([{ slot: "bottom", blocks: st.payload.blocks }])}>{st.name}</Button>
              <Button size="sm" variant="ghost" onClick={async () => { await api.blockSetDelete(connectionId, st.id); void load(); }}>Delete</Button>
            </div>
          ))}
          {!shown.length ? <p className={styles.small}>None saved for this <Term tech="ir.model">record type</Term> yet.</p> : null}
          <div className={styles.inline}>
            <input aria-label="Block set name" value={name} maxLength={80} placeholder="Name this set" onChange={(e) => setName(e.target.value)} />
            <Button size="sm" variant="ghost" disabled={!name.trim() || !blockCount(placements)} onClick={async () => {
              try {
                await api.blockSetSave(connectionId, model, name.trim(), placements.flatMap((p) => p.blocks));
                setName("");
                void load();
              } catch (e) {
                noteWriteRefusal(e);
                toast.error(e instanceof Error ? e.message : "Couldn't save.");
              }
            }}>Save current blocks</Button>
          </div>
        </>
      ) : null}
    </div>
  );
}
