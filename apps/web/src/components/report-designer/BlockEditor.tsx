"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import type { Condition } from "@/lib/api/view-engine";
import type { BlockType, LineColumn, Placement, ReportBlock2b, Slot2b } from "@/lib/api/view-engine-2b";
import { BLOCK_LABELS, moveBlock, updateBlock } from "@/lib/viewDesigner2b";
import { Note } from "../view-designer/Note";
import styles from "./ReportDesigner.module.css";

export type FieldOpt = { name: string; label: string; type: string };

export type BlockContext = {
  fields: FieldOpt[];
  lineFields: string[];
  loadColumns: (field: string) => Promise<LineColumn[]>;
};

const TEXTISH = ["char", "text", "date", "datetime", "monetary", "float", "integer", "many2one", "selection", "html", "boolean"];
const CODEISH = ["char"];
const PICTURE = ["binary", "image"];

/** Plain words for a block condition (the server builds the real check). */
export function conditionWords(c: Condition | null | undefined, fields: FieldOpt[]): string {
  if (!c?.rules.length) return "";
  const label = (f: string) => fields.find((x) => x.name === f)?.label ?? f;
  const op: Record<string, string> = { set: "is filled in", not_set: "is empty", is_true: "is ticked", is_false: "is not ticked", is: "is", is_not: "is not", gt: "is more than", lt: "is less than" };
  return c.rules.map((r) => `${label(r.field)} ${op[r.op] ?? r.op}${r.value !== undefined && r.value !== "" ? ` ${String(r.value)}` : ""}`).join(c.match === "any" ? " or " : " and ");
}

function FieldSelect({ value, onChange, fields, types, label, allowEmpty }: { value: string; onChange: (v: string) => void; fields: FieldOpt[]; types: string[]; label: string; allowEmpty?: boolean }) {
  const opts = fields.filter((f) => types.includes(f.type));
  return (
    <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)}>
      {allowEmpty || !opts.some((f) => f.name === value) ? <option value="">Choose…</option> : null}
      {opts.map((f) => <option key={f.name} value={f.name}>{f.label}</option>)}
    </select>
  );
}

function OnlyWhen({ block, onChange, fields, n }: { block: ReportBlock2b; onChange: (b: ReportBlock2b) => void; fields: FieldOpt[]; n: number }) {
  const [open, setOpen] = useState(false);
  const [field, setField] = useState("");
  const [op, setOp] = useState("set");
  const [value, setValue] = useState("");
  const words = conditionWords(block.condition, fields);
  const t = fields.find((f) => f.name === field)?.type ?? "";
  const canCompare = ["char", "selection", "integer", "float", "monetary"].includes(t);
  if (words) {
    return (
      <p className={styles.small}>
        Only when {words}{" "}
        <Button size="sm" variant="ghost" onClick={() => onChange({ ...block, condition: null })}>Always show</Button>
      </p>
    );
  }
  if (!open) return <Button size="sm" variant="ghost" onClick={() => setOpen(true)}>Only show when…</Button>;
  return (
    <form
      className={styles.inline}
      onSubmit={(e) => {
        e.preventDefault();
        if (!field) return;
        const num = ["integer", "float", "monetary"].includes(t);
        const rule = ["set", "not_set"].includes(op) ? { field, op } : { field, op, value: num ? Number(value) : value };
        onChange({ ...block, condition: { match: "all", rules: [rule] } });
        setOpen(false);
      }}
    >
      <FieldSelect value={field} onChange={setField} fields={fields} types={[...TEXTISH, "one2many", "many2many", "binary"]} label={`Only when field, block ${n}`} allowEmpty />
      <select aria-label={`Only when check, block ${n}`} value={op} onChange={(e) => setOp(e.target.value)}>
        <option value="set">is filled in</option>
        <option value="not_set">is empty</option>
        {canCompare ? <option value="is">is</option> : null}
        {canCompare ? <option value="is_not">is not</option> : null}
        {["integer", "float", "monetary"].includes(t) ? <option value="gt">is more than</option> : null}
      </select>
      {["is", "is_not", "gt"].includes(op) ? <Input aria-label={`Only when value, block ${n}`} value={value} onChange={(e) => setValue(e.target.value)} /> : null}
      <Button size="sm" type="submit" disabled={!field}>Set</Button>
      <Button size="sm" variant="ghost" type="button" onClick={() => setOpen(false)}>Cancel</Button>
    </form>
  );
}

function LinesTable({ block, onChange, ctx, n }: { block: Extract<ReportBlock2b, { type: "line_table" }>; onChange: (b: ReportBlock2b) => void; ctx: BlockContext; n: number }) {
  const [cols, setCols] = useState<LineColumn[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    setCols(null);
    setErr(null);
    if (!block.field) return;
    let live = true;
    ctx.loadColumns(block.field).then((c) => live && setCols(c)).catch((e) => live && setErr(e instanceof Error ? e.message : "Couldn't load the line fields."));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [block.field]);
  const chosen = new Map(block.columns.map((c) => [c.field, c]));
  const toggle = (c: LineColumn, on: boolean) => {
    const next = on ? [...block.columns, { field: c.name, label: c.label, sum: false }] : block.columns.filter((x) => x.field !== c.name);
    onChange({ ...block, columns: next.slice(0, 10) });
  };
  const fieldLabel = (f: string) => ctx.fields.find((x) => x.name === f)?.label ?? f;
  return (
    <div className={styles.stack}>
      <select aria-label={`Lines, block ${n}`} value={block.field} onChange={(e) => onChange({ ...block, field: e.target.value, columns: [] })}>
        <option value="">Which lines…</option>
        {ctx.lineFields.map((f) => <option key={f} value={f}>{fieldLabel(f)}</option>)}
      </select>
      {err ? <Note tone="danger" role="alert">{err}</Note> : null}
      {cols ? (
        <ul className={styles.blocks} aria-label={`Columns, block ${n}`}>
          {cols.map((c) => (
            <li key={c.name} className={styles.inline}>
              <label className={styles.inline}>
                <input type="checkbox" checked={chosen.has(c.name)} disabled={!chosen.has(c.name) && block.columns.length >= 10} onChange={(e) => toggle(c, e.target.checked)} />
                {c.label}
              </label>
              {chosen.has(c.name) && c.can_total ? (
                <label className={styles.inline + " " + styles.small}>
                  <input
                    type="checkbox"
                    checked={Boolean(chosen.get(c.name)?.sum)}
                    onChange={(e) => onChange({ ...block, columns: block.columns.map((x) => (x.field === c.name ? { ...x, sum: e.target.checked } : x)) })}
                  />
                  total
                </label>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
      {block.columns.some((c) => c.sum) ? (
        <Input aria-label={`Totals label, block ${n}`} value={block.totals_label ?? ""} placeholder="Total" maxLength={40} onChange={(e) => onChange({ ...block, totals_label: e.target.value })} />
      ) : null}
    </div>
  );
}

export function BlockEditor({ block, n, ctx, onChange }: { block: ReportBlock2b; n: number; ctx: BlockContext; onChange: (b: ReportBlock2b) => void }) {
  const label = BLOCK_LABELS[block.type];
  switch (block.type) {
    case "text":
    case "heading":
      return (
        <div className={styles.inline}>
          <Input aria-label={`${label} ${n}`} value={block.text} maxLength={500} placeholder={block.type === "text" ? "Thank you for your business…" : "Payment details…"} onChange={(e) => onChange({ ...block, text: e.target.value })} />
          {block.type === "heading" ? (
            <select aria-label={`Heading size ${n}`} value={block.level ?? 3} onChange={(e) => onChange({ ...block, level: Number(e.target.value) })}>
              <option value={2}>Large</option>
              <option value={3}>Medium</option>
              <option value={4}>Small</option>
            </select>
          ) : null}
        </div>
      );
    case "field":
    case "label_field":
      return (
        <div className={styles.inline}>
          <FieldSelect value={block.field} onChange={(field) => onChange({ ...block, field })} fields={ctx.fields} types={TEXTISH} label={`Field ${n}`} />
          {block.type === "label_field" ? <Input aria-label={`Label ${n}`} value={block.label ?? ""} placeholder="Label (optional)" maxLength={80} onChange={(e) => onChange({ ...block, label: e.target.value })} /> : null}
        </div>
      );
    case "qr":
    case "barcode":
      return <FieldSelect value={block.field} onChange={(field) => onChange({ ...block, field })} fields={ctx.fields} types={CODEISH} label={`${label} from field ${n}`} />;
    case "signature":
      return (
        <div className={styles.inline}>
          <FieldSelect value={block.field} onChange={(field) => onChange({ ...block, field })} fields={ctx.fields} types={PICTURE} label={`Signature field ${n}`} />
          <FieldSelect value={block.signed_by ?? ""} onChange={(signed_by) => onChange({ ...block, signed_by })} fields={ctx.fields} types={["char"]} label={`Signed by ${n}`} allowEmpty />
          <Input aria-label={`Signature label ${n}`} value={block.label ?? ""} placeholder="Signature" maxLength={80} onChange={(e) => onChange({ ...block, label: e.target.value })} />
        </div>
      );
    case "image_field":
      return <FieldSelect value={block.field} onChange={(field) => onChange({ ...block, field })} fields={ctx.fields} types={PICTURE} label={`Picture field ${n}`} />;
    case "line_table":
      return <LinesTable block={block} onChange={onChange} ctx={ctx} n={n} />;
    case "watermark":
      return (
        <div className={styles.inline}>
          <Input aria-label={`Watermark text ${n}`} value={block.text} maxLength={30} onChange={(e) => onChange({ ...block, text: e.target.value })} />
          <select aria-label={`Watermark colour ${n}`} value={block.colour ?? "grey"} onChange={(e) => onChange({ ...block, colour: e.target.value as "grey" })}>
            <option value="grey">Grey</option>
            <option value="red">Red</option>
            <option value="blue">Blue</option>
            <option value="green">Green</option>
          </select>
        </div>
      );
    case "spacer":
      return (
        <select aria-label={`Space size ${n}`} value={block.size ?? "medium"} onChange={(e) => onChange({ ...block, size: e.target.value as "medium" })}>
          <option value="small">Small</option>
          <option value="medium">Medium</option>
          <option value="large">Large</option>
        </select>
      );
    default:
      return null;
  }
}

/** True when a block has what it needs to print (drafts wait until then). */
export function blockReady(b: ReportBlock2b): boolean {
  switch (b.type) {
    case "text":
    case "heading":
    case "watermark":
      return Boolean(b.text.trim());
    case "line_table":
      return Boolean(b.field) && b.columns.length > 0;
    case "field":
    case "label_field":
    case "qr":
    case "barcode":
    case "signature":
    case "image_field":
      return Boolean(b.field);
    default:
      return true;
  }
}

/** Slots in reading order: top, the places inside the document, bottom. */
export function orderedSlots(slots: Slot2b[]): Slot2b[] {
  const rank = (s: Slot2b) => (s.id === "top" ? 0 : s.id === "bottom" ? 2 : 1);
  return [...slots].sort((a, b) => rank(a) - rank(b));
}

type EditorProps = {
  slots: Slot2b[];
  placements: Placement[];
  activeSlot: string;
  onActiveSlot: (id: string) => void;
  onChange: (p: Placement[]) => void;
  ctx: BlockContext;
  stockLabel: string;
};

/** The paper: blocks grouped by where they go, around Odoo's own content. */
export function PlacementsEditor({ slots, placements, activeSlot, onActiveSlot, onChange, ctx, stockLabel }: EditorProps) {
  const bySlot = new Map(placements.map((p) => [p.slot, p.blocks]));
  let counter = 0;
  const section = (sl: Slot2b) => {
    const blocks = bySlot.get(sl.id) ?? [];
    if (!blocks.length && sl.id !== activeSlot) return null;
    return (
      <section key={sl.id} className={styles.stack} aria-label={`Blocks: ${sl.label}`} data-slot={sl.id}>
        <button type="button" className={styles.small} aria-pressed={sl.id === activeSlot} onClick={() => onActiveSlot(sl.id)}>{sl.label}</button>
        {blocks.length ? (
          <ol className={styles.blocks} data-testid={`rd-blocks-${sl.id}`}>
            {blocks.map((b, i) => {
              counter += 1;
              const n = counter;
              const set = (nb: ReportBlock2b | null) => onChange(updateBlock(placements, sl.id, i, nb));
              return (
                <li key={`${sl.id}-${i}`} className={styles.block}>
                  <span className={styles.small}>{BLOCK_LABELS[b.type as BlockType]}</span>
                  <BlockEditor block={b} n={n} ctx={ctx} onChange={set} />
                  <OnlyWhen block={b} onChange={set} fields={ctx.fields} n={n} />
                  <div className={styles.inline}>
                    <Button size="sm" variant="ghost" aria-label={`Move block ${n} up`} disabled={i === 0} onClick={() => onChange(moveBlock(placements, sl.id, i, -1))}>↑</Button>
                    <Button size="sm" variant="ghost" aria-label={`Move block ${n} down`} disabled={i === blocks.length - 1} onClick={() => onChange(moveBlock(placements, sl.id, i, 1))}>↓</Button>
                    <Button size="sm" variant="ghost" onClick={() => set(null)}>Remove</Button>
                  </div>
                </li>
              );
            })}
          </ol>
        ) : (
          <p className={styles.dropHint}>New content appears here. Add a block from the left.</p>
        )}
      </section>
    );
  };
  const ordered = orderedSlots(slots);
  return (
    <>
      {ordered.filter((s) => s.id === "top").map(section)}
      <p className={styles.stockContent}>{stockLabel}</p>
      {ordered.filter((s) => s.id !== "top").map(section)}
    </>
  );
}
