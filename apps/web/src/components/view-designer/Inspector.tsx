"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import type { EngineCompileOut, EngineNode, EngineOp } from "@/lib/api/view-engine";
import { nodeName, plainTag, visibilityChips, type TreeIndex } from "@/lib/viewEngineOps";
import { Note } from "../view-designer/Note";
import styles from "./ViewDesigner.module.css";

type InspectorProps = {
  node: EngineNode | null;
  index: TreeIndex;
  onOp: (op: EngineOp) => void;
  compiled: EngineCompileOut | null;
  showCode: boolean;
  onToggleCode: () => void;
};

const yes = (v: string | undefined) => v === "1" || v === "True";
const SETTABLE: Record<string, string[]> = {
  field: ["string", "invisible", "readonly", "required"],
  group: ["string", "invisible"],
  page: ["string", "invisible"],
  button: ["string", "invisible"],
  notebook: ["invisible"],
  div: ["invisible"],
};

/** Properties of the selected item. Every change is checked by the server. */
export function Inspector({ node, index, onOp, compiled, showCode, onToggleCode }: InspectorProps) {
  const [label, setLabel] = useState(node?.attrs.string ?? node?.label ?? "");
  useEffect(() => setLabel(node?.attrs.string ?? node?.label ?? ""), [node]);

  if (!node) {
    return (
      <div className={styles.panelBody} data-testid="vd-inspector">
        <p className={styles.muted}>Select a field, group or tab on the screen to change it.</p>
      </div>
    );
  }
  const can = SETTABLE[node.tag] ?? [];
  const locked = !node.anchor;
  const parentId = index.parentOf.get(node.id);
  const parent = parentId ? index.byId.get(parentId) : undefined;
  const setAttr = (attr: string, value: string) => onOp({ op: "set_attr", node: node.id, attr, value });

  return (
    <div className={styles.panelBody} data-testid="vd-inspector">
      <h2 className={styles.panelTitle}>{nodeName(node)}</h2>
      <p className={styles.muted}>{node.kind === "block" ? "Odoo element" : plainTag(node.tag)}{node.field_type ? `, ${node.field_type}` : ""}</p>
      {locked ? (
        <Note tone="warning" role="note">
          This can&apos;t be changed safely. {node.locked_reason}
        </Note>
      ) : null}
      {!locked && node.anchor_note ? <p className={styles.muted} role="note">{node.anchor_note}</p> : null}

      <section className={styles.section} aria-labelledby="vd-props">
        <h3 id="vd-props" className={styles.sectionTitle}>Properties</h3>
        {can.includes("string") ? (
          <form
            className={styles.inline}
            onSubmit={(e) => {
              e.preventDefault();
              if (label.trim() && label !== (node.attrs.string ?? node.label)) setAttr("string", label.trim());
            }}
          >
            <label className={styles.fieldLabel} htmlFor="vd-label">Label</label>
            <Input id="vd-label" value={label} disabled={locked} maxLength={80} onChange={(e) => setLabel(e.target.value)} />
            <Button size="sm" type="submit" disabled={locked || !label.trim()}>Rename</Button>
          </form>
        ) : null}
        {(["required", "readonly", "invisible"] as const)
          .filter((a) => can.includes(a))
          .map((attr) => {
            const text = { required: "Must be filled in", readonly: "Read-only", invisible: "Hidden" }[attr];
            const raw = node.attrs[attr];
            const dynamic = raw !== undefined && !["0", "1", "True", "False"].includes(raw);
            return (
              <label key={attr} className={styles.check}>
                <input
                  type="checkbox"
                  checked={yes(raw)}
                  disabled={locked || dynamic}
                  onChange={(e) => (attr === "invisible" && e.target.checked ? onOp({ op: "hide", node: node.id }) : setAttr(attr, e.target.checked ? "1" : "0"))}
                />
                {text}
                {dynamic ? <span className={styles.muted}> (set by a rule)</span> : null}
              </label>
            );
          })}
        {!can.includes("invisible") && node.kind !== "root" && node.tag !== "sheet" ? (
          <Button size="sm" variant="ghost" disabled={locked} onClick={() => onOp({ op: "hide", node: node.id })}>
            Hide
          </Button>
        ) : null}
      </section>

      <section className={styles.section} aria-labelledby="vd-who-now">
        <h3 id="vd-who-now" className={styles.sectionTitle}>Right now</h3>
        <ul className={styles.chipList}>
          {visibilityChips(node).map((c) => (
            <li key={c} className={styles.chip}>{c}</li>
          ))}
        </ul>
      </section>

      {!locked && node.tag === "field" && parent ? (
        <section className={styles.section} aria-labelledby="vd-arrange">
          <h3 id="vd-arrange" className={styles.sectionTitle}>Arrange</h3>
          <Button size="sm" variant="ghost" onClick={() => onOp({ op: "wrap", nodes: [node.id], kind: "group", label: "New group" })}>
            Put in a new group
          </Button>
          {parent.tag === "page" ? (
            <Button size="sm" variant="ghost" onClick={() => onOp({ op: "wrap", nodes: [node.id], kind: "page", label: "New tab" })}>
              Put on a new tab
            </Button>
          ) : null}
        </section>
      ) : null}
      {!locked && node.tag === "group" && parent?.tag === "sheet" ? (
        <section className={styles.section}>
          <Button size="sm" variant="ghost" onClick={() => onOp({ op: "wrap", nodes: [node.id], kind: "notebook", label: "New tab" })}>
            Put on a tab
          </Button>
        </section>
      ) : null}

      <section className={styles.section}>
        <label className={styles.check}>
          <input type="checkbox" checked={showCode} onChange={onToggleCode} />
          Show code
        </label>
        {showCode ? (
          <pre className={styles.code} data-testid="vd-code">
            {compiled?.arch ?? "No changes yet."}
          </pre>
        ) : null}
      </section>
    </div>
  );
}
