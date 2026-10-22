"use client";

import { useEffect, useMemo, useState } from "react";
import { FillBar } from "@/components/ui/craft";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import type { EngineField } from "@/lib/api/view-engine";
import { fieldsNotOnScreen, type TreeIndex } from "@/lib/viewEngineOps";
import { FIELD_DRAG_TYPE } from "./EngineCanvas";
import styles from "./ViewDesigner.module.css";

type FieldsPanelProps = {
  index: TreeIndex;
  fields: Record<string, EngineField>;
  selectedLabel: string | null;
  onAdd: (field: string) => void;
  connectionId?: string;
  model?: string | null;
};

/** Fields not yet on the screen. Drag onto the canvas, or add after the selected item. */
export function FieldsPanel({ index, fields, selectedLabel, onAdd, connectionId, model }: FieldsPanelProps) {
  const [query, setQuery] = useState("");
  const list = useMemo(() => fieldsNotOnScreen(index, fields, query), [index, fields, query]);
  const [fill, setFill] = useState<Record<string, number | null>>({});
  const names = useMemo(() => fieldsNotOnScreen(index, fields, "").slice(0, 40).map((f) => f.name).join(","), [index, fields]);
  useEffect(() => {
    if (!connectionId || !model || !names) return;
    let alive = true;
    api.fieldFill(connectionId, model, names.split(",")).then((r) => alive && setFill(r.fill)).catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [connectionId, model, names]);
  return (
    <div className={styles.panelBody} data-testid="vd-fields">
      <label className={styles.fieldLabel} htmlFor="vd-field-search">
        Find a field
      </label>
      <Input id="vd-field-search" value={query} placeholder="Phone, deadline, tags…" onChange={(e) => setQuery(e.target.value)} />
      {list.length === 0 ? <p className={styles.muted}>Every matching field is already on this screen.</p> : null}
      <ul className={styles.fieldList}>
        {list.map((f) => (
          <li
            key={f.name}
            draggable
            onDragStart={(e) => {
              e.dataTransfer.setData(FIELD_DRAG_TYPE, f.name);
              e.dataTransfer.effectAllowed = "copy";
            }}
            className={styles.fieldRow}
          >
            <span>{f.label}<FillBar ratio={fill[f.name]} label={f.label} /></span>
            <Button
              size="sm"
              variant="ghost"
              disabled={!selectedLabel}
              title={selectedLabel ? `Add after ${selectedLabel}` : "Select an item on the screen first"}
              onClick={() => onAdd(f.name)}
            >
              Add
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}
