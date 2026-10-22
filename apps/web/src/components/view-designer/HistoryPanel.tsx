"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";
import type { EngineNode, EngineViewType, HistoryVersion, Marker } from "@/lib/api/view-engine";
import { markerSummary } from "@/lib/viewDesigner2a";
import { Note } from "../view-designer/Note";
import styles from "./ViewDesigner.module.css";

type Props = {
  connectionId: string;
  model: string;
  viewType: EngineViewType;
  refreshKey: number;
  onMarkers: (markers: Record<string, Marker> | null) => void;
  onScrub: (view: { tree: EngineNode; label: string } | null) => void;
  onRestored: () => void;
  errorText: (err: unknown) => string;
};

const ACTION_WORDS: Record<string, string> = { publish: "Published", revert: "Undone", restore: "Restored", remove: "Removed" };

function when(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/** History: named versions, compare with now, restore (with undo) and a scrubber. */
export function HistoryPanel({ connectionId, model, viewType, refreshKey, onMarkers, onScrub, onRestored, errorText }: Props) {
  const [versions, setVersions] = useState<HistoryVersion[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [naming, setNaming] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [compareLine, setCompareLine] = useState<{ id: string; text: string; changes: string[] } | null>(null);
  const [scrub, setScrub] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const out = await api.historyList(connectionId, model, viewType);
      setVersions(out.versions);
      setError(null);
    } catch (err) {
      setError(errorText(err));
    }
  }, [connectionId, model, viewType, errorText]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  // Oldest on the left of the scrubber, newest on the right.
  const ordered = [...versions].reverse();

  const compare = async (v: HistoryVersion) => {
    try {
      const out = await api.historyCompare(connectionId, model, viewType, v.id, "current");
      onMarkers(out.markers);
      setCompareLine({ id: v.id, text: markerSummary(out.markers), changes: out.changes });
    } catch (err) {
      toast.error(errorText(err));
    }
  };

  const restore = async (v: HistoryVersion) => {
    try {
      const out = await api.historyRestore(connectionId, v.id);
      toast.success(`Restored ${v.label ?? "that version"}`, {
        duration: 10000,
        action: {
          label: "Undo",
          onClick: () =>
            void api
              .engineRevert(connectionId, {
                model,
                view_type: viewType,
                layer_view_id: out.layer_view_id,
                mode: out.previous_arch ? "restore" : "deactivate",
                restore_arch: out.previous_arch,
              })
              .then(() => {
                toast.success("Restore undone");
                onRestored();
                void load();
              })
              .catch((err) => toast.error(errorText(err))),
        },
      });
      onRestored();
      await load();
    } catch (err) {
      toast.error(errorText(err));
    }
  };

  const scrubTo = async (i: number) => {
    setScrub(i);
    const v = ordered[i];
    if (!v) return;
    if (i === ordered.length - 1) {
      onScrub(null);
      return;
    }
    try {
      const out = await api.historyTree(connectionId, v.id);
      onScrub({ tree: out.tree, label: v.label ?? `${ACTION_WORDS[v.action] ?? v.action} ${when(v.created_at)}` });
    } catch (err) {
      toast.error(errorText(err));
    }
  };

  return (
    <div className={styles.panelBody} data-testid="vd-history">
      {error ? <Note tone="danger" role="alert">{error}</Note> : null}
      {!versions.length && !error ? <p className={styles.muted}>No published versions of this screen yet.</p> : null}
      {ordered.length > 1 ? (
        <label className={styles.stack}>
          <span className={styles.fieldLabel}>Step through history</span>
          <input
            type="range"
            className={styles.scrubber}
            min={0}
            max={ordered.length - 1}
            value={scrub ?? ordered.length - 1}
            aria-valuetext={ordered[scrub ?? ordered.length - 1]?.label ?? when(ordered[scrub ?? ordered.length - 1]?.created_at ?? null)}
            onChange={(e) => void scrubTo(Number(e.target.value))}
          />
        </label>
      ) : null}
      <ul className={styles.list}>
        {versions.map((v) => (
          <li key={v.id} className={styles.stack} data-testid="vd-history-row">
            <div className={styles.listItem}>
              <span>
                <strong>{v.label ?? `${ACTION_WORDS[v.action] ?? v.action}`}</strong>{" "}
                <span className={styles.muted}>{when(v.created_at)}</span>
              </span>
            </div>
            {v.summary.length ? <p className={styles.muted}>{v.summary.slice(0, 3).join(", ")}</p> : null}
            {naming === v.id ? (
              <form
                className={styles.row}
                onSubmit={(e) => {
                  e.preventDefault();
                  void api
                    .historyName(connectionId, v.id, name.trim())
                    .then(() => {
                      setNaming(null);
                      void load();
                    })
                    .catch((err) => toast.error(errorText(err)));
                }}
              >
                <Input aria-label="Version name" value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
                <Button size="sm" type="submit" disabled={!name.trim()}>Save</Button>
              </form>
            ) : null}
            <div className={styles.row}>
              <Button size="sm" variant="ghost" onClick={() => { setNaming(v.id); setName(v.label ?? ""); }}>Name</Button>
              <Button size="sm" variant="ghost" onClick={() => void compare(v)}>Compare with now</Button>
              <Button size="sm" variant="ghost" onClick={() => void restore(v)}>Restore</Button>
            </div>
            {compareLine?.id === v.id ? (
              <div className={styles.stack}>
                <p>{compareLine.text}</p>
                <ul className={styles.list}>
                  {compareLine.changes.slice(0, 8).map((c) => <li key={c} className={styles.muted}>{c}</li>)}
                </ul>
                <Button size="sm" variant="ghost" onClick={() => { setCompareLine(null); onMarkers(null); }}>Clear markers</Button>
              </div>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
