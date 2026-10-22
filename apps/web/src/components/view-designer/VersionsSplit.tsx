"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import type { EngineOp, EngineViewType, VersionRow } from "@/lib/api/view-engine";
import { indexTree } from "@/lib/viewEngineOps";
import { EngineCanvas } from "./EngineCanvas";
import { Note } from "../view-designer/Note";
import styles from "./ViewDesigner.module.css";

type Props = {
  connectionId: string;
  model: string;
  viewType: EngineViewType;
  ops: EngineOp[];
  width: number;
  onClose: () => void;
  errorText: (err: unknown) => string;
};

const noop = () => undefined;

/** Version side by side: the same changes on standard Odoo 17, 18, 19 and 20, with plain flags. */
export function VersionsSplit({ connectionId, model, viewType, ops, width, onClose, errorText }: Props) {
  const [rows, setRows] = useState<VersionRow[] | null>(null);
  const [picked, setPicked] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setRows(null);
    api
      .versions(connectionId, { model, view_type: viewType, ops })
      .then((out) => {
        if (!live) return;
        setRows(out.versions);
        setPicked((cur) => (cur.length ? cur : out.versions.filter((v) => v.available).map((v) => v.version)));
      })
      .catch((err) => live && setError(errorText(err)));
    return () => {
      live = false;
    };
  }, [connectionId, model, viewType, ops, errorText]);

  return (
    <div className={styles.stack} data-testid="vd-versions">
      <div className={styles.banner}>
        <span>Your changes on standard Odoo, side by side</span>
        <span className={styles.row}>
          {(rows ?? []).map((v) => (
            <label key={v.version} className={styles.check}>
              <input
                type="checkbox"
                checked={picked.includes(v.version)}
                disabled={!v.available}
                onChange={(e) => setPicked((p) => (e.target.checked ? [...p, v.version].sort() : p.filter((x) => x !== v.version)))}
              />
              Odoo {v.version}
            </label>
          ))}
          <Button size="sm" variant="ghost" onClick={onClose}>Close</Button>
        </span>
      </div>
      {error ? <Note tone="danger" role="alert">{error}</Note> : null}
      {!rows && !error ? <Note tone="busy" role="status">Checking each version…</Note> : null}
      <div className={styles.split}>
        {(rows ?? [])
          .filter((v) => picked.includes(v.version))
          .map((v) => (
            <div key={v.version} className={styles.splitCol} data-testid={`vd-version-${v.version}`}>
              <strong>
                Odoo {v.version}
                {v.current ? " (this database)" : ""}
              </strong>
              {v.flags.length ? v.flags.map((f) => <Note tone="warning" key={f}>{f}</Note>) : <Note tone="success">Works on this version.</Note>}
              {v.tree ? (
                <div style={{ maxWidth: width }}>
                  <EngineCanvas tree={v.tree} index={indexTree(v.tree)} record={null} selectedId={null} onSelect={noop} onMove={noop} onInsertField={noop} readOnly />
                </div>
              ) : null}
            </div>
          ))}
      </div>
    </div>
  );
}
