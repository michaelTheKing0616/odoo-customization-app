"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";
import type { Condition, EngineField, EngineNode, EngineOp, EngineViewType } from "@/lib/api/view-engine";
import type { Widget } from "@/lib/api/view-engine-2b";
import styles from "./ViewDesigner.module.css";

type Common = {
  connectionId: string;
  model: string;
  viewType: EngineViewType;
  viewId: number | null;
  fields: Record<string, EngineField>;
  onOp: (op: EngineOp) => void;
  onOps: (ops: EngineOp[], summary: string) => void;
  errorText: (err: unknown) => string;
};

const DECORATIONS: Array<[string, string]> = [
  ["danger", "Red"],
  ["warning", "Amber"],
  ["success", "Green"],
  ["info", "Blue"],
  ["muted", "Grey"],
  ["primary", "Highlight"],
  ["bf", "Bold"],
  ["it", "Italic"],
];

/** Simple one-rule condition picker: field is / is set (the server validates and words it). */
function OneRule({ fields, onPick, label }: { fields: Record<string, EngineField>; onPick: (c: Condition) => void; label: string }) {
  const [field, setField] = useState("");
  const [op, setOp] = useState("is");
  const [value, setValue] = useState("");
  const names = Object.entries(fields)
    .filter(([, m]) => ["selection", "char", "boolean", "integer", "float", "monetary", "many2one"].includes(m.type ?? ""))
    .sort((a, b) => (a[1].string ?? a[0]).localeCompare(b[1].string ?? b[0]));
  const t = fields[field]?.type;
  const parsed = (): unknown => (["integer", "float", "monetary", "many2one"].includes(t ?? "") ? Number(value) : value);
  return (
    <form
      className={styles.row}
      onSubmit={(e) => {
        e.preventDefault();
        if (!field) return;
        const rule = op === "set" || op === "not_set" || op === "is_true" || op === "is_false" ? { field, op } : { field, op, value: parsed() };
        onPick({ match: "all", rules: [rule] });
      }}
    >
      <select className={styles.select} aria-label="When field" value={field} onChange={(e) => setField(e.target.value)}>
        <option value="">When…</option>
        {names.map(([n, m]) => <option key={n} value={n}>{m.string ?? n}</option>)}
      </select>
      <select className={styles.select} aria-label="Condition" value={op} onChange={(e) => setOp(e.target.value)}>
        {t === "boolean" ? (
          <>
            <option value="is_true">is ticked</option>
            <option value="is_false">is not ticked</option>
          </>
        ) : (
          <>
            <option value="is">is</option>
            <option value="is_not">is not</option>
            <option value="set">is filled in</option>
            <option value="not_set">is empty</option>
            {["integer", "float", "monetary"].includes(t ?? "") ? <option value="gt">is more than</option> : null}
          </>
        )}
      </select>
      {["is", "is_not", "gt"].includes(op) && t !== "boolean" ? (
        <Input aria-label="Value" value={value} onChange={(e) => setValue(e.target.value)} placeholder={t === "many2one" ? "record id" : "value"} />
      ) : null}
      <Button size="sm" type="submit" disabled={!field}>{label}</Button>
    </form>
  );
}

/** Card colour flags accept only these Odoo colours (no bold/italic). */
const CARD_COLOURS = DECORATIONS.filter(([v]) => ["danger", "warning", "success", "info", "muted", "primary"].includes(v));

/** Field settings Studio offers: display style (widget), hint, tooltip, column settings, default value. */
export function FieldExtras({ node, rootTag, ...c }: Common & { node: EngineNode; rootTag: string }) {
  const [widgets, setWidgets] = useState<Widget[]>([]);
  const [placeholder, setPlaceholder] = useState(node.attrs.placeholder ?? "");
  const [help, setHelp] = useState(node.attrs.help ?? "");
  const [def, setDef] = useState<{ value: unknown; set: boolean } | null>(null);
  const [defDraft, setDefDraft] = useState("");
  const field = node.name ?? "";
  const meta = c.fields[field] ?? {};
  const isList = rootTag === "list" || rootTag === "tree";
  const numeric = ["integer", "float", "monetary"].includes(meta.type ?? "");

  useEffect(() => {
    setPlaceholder(node.attrs.placeholder ?? "");
    setHelp(node.attrs.help ?? "");
    if (!meta.type) return;
    api.widgets(c.connectionId, meta.type).then((o) => setWidgets(o.widgets)).catch(() => setWidgets([]));
    api.defaultGet(c.connectionId, c.model, field).then((d) => { setDef(d); setDefDraft(d.value == null ? "" : String(d.value)); }).catch(() => setDef(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [node.id, meta.type, c.connectionId, c.model]);

  const set = (attr: string, value: string) => c.onOp({ op: "set_attr", node: node.id, attr, value });
  const locked = !node.anchor;

  return (
    <section className={styles.section} aria-label="Display and defaults" data-testid="vd-field-extras">
      <h3 className={styles.sectionTitle}>Display</h3>
      {widgets.length ? (
        <label className={styles.fieldLabel}>
          Show as
          <select className={styles.select} value={node.attrs.widget ?? ""} disabled={locked} onChange={(e) => set("widget", e.target.value)} data-testid="vd-widget">
            <option value="">Odoo&apos;s default</option>
            {widgets.map((w) => <option key={w.name} value={w.name}>{w.label}</option>)}
          </select>
        </label>
      ) : null}
      {!isList ? (
        <>
          <label className={styles.fieldLabel}>
            Hint inside the box
            <Input value={placeholder} disabled={locked} maxLength={80} onChange={(e) => setPlaceholder(e.target.value)}
              onBlur={() => placeholder !== (node.attrs.placeholder ?? "") && set("placeholder", placeholder)} />
          </label>
          <label className={styles.fieldLabel}>
            Tooltip
            <Input value={help} disabled={locked} maxLength={300} onChange={(e) => setHelp(e.target.value)}
              onBlur={() => help !== (node.attrs.help ?? "") && set("help", help)} />
          </label>
        </>
      ) : (
        <>
          <label className={styles.fieldLabel}>
            Column
            <select className={styles.select} value={node.attrs.optional ?? ""} disabled={locked} onChange={(e) => set("optional", e.target.value)}>
              <option value="">Always shown</option>
              <option value="show">Shown, can be hidden</option>
              <option value="hide">Hidden, can be shown</option>
            </select>
          </label>
          <label className={styles.fieldLabel}>
            Width
            <Input defaultValue={node.attrs.width ?? ""} placeholder="e.g. 120px" disabled={locked} onBlur={(e) => e.target.value !== (node.attrs.width ?? "") && set("width", e.target.value)} />
          </label>
          {numeric ? (
            <label className={styles.check}>
              <input type="checkbox" checked={Boolean(node.attrs.sum)} disabled={locked}
                onChange={(e) => set("sum", e.target.checked ? `Total ${meta.string ?? field}` : "")} /> Show a total under the column
            </label>
          ) : null}
        </>
      )}

      <h3 className={styles.sectionTitle}>Default value</h3>
      <p className={styles.muted}>Filled in on new records (saved in Odoo as a default for everyone).</p>
      {meta.type === "boolean" ? (
        <select className={styles.select} aria-label="Default" value={defDraft} onChange={(e) => setDefDraft(e.target.value)}>
          <option value="">No default</option>
          <option value="true">Ticked</option>
          <option value="false">Not ticked</option>
        </select>
      ) : (
        <Input aria-label="Default" value={defDraft} onChange={(e) => setDefDraft(e.target.value)} placeholder={meta.type === "many2one" ? "record id" : "value"} />
      )}
      <div className={styles.row}>
        <Button
          size="sm"
          onClick={async () => {
            const clear = defDraft === "";
            const value = meta.type === "boolean" ? defDraft === "true" : ["integer", "float", "monetary", "many2one"].includes(meta.type ?? "") ? Number(defDraft) : defDraft;
            try {
              const out = await api.defaultSet(c.connectionId, c.model, field, value, clear);
              toast.success(clear ? "Default removed" : "Default saved", {
                action: {
                  label: "Undo",
                  onClick: () => void api.defaultSet(c.connectionId, c.model, field, out.previous, !out.had_previous),
                },
              });
              setDef({ value: clear ? null : value, set: !clear });
            } catch (err) {
              toast.error(c.errorText(err));
            }
          }}
          data-testid="vd-default-save"
        >
          {def?.set ? "Change default" : "Set default"}
        </Button>
      </div>
    </section>
  );
}

/** Save a group or tab as a reusable section (structure and labels only). */
export function SaveSection({ node, ...c }: Common & { node: EngineNode }) {
  const [name, setName] = useState("");
  if (!["group", "page", "notebook"].includes(node.tag)) return null;
  return (
    <form
      className={styles.row}
      onSubmit={async (e) => {
        e.preventDefault();
        try {
          await api.sectionSave(c.connectionId, { model: c.model, view_type: c.viewType, view_id: c.viewId }, node.id, name.trim());
          toast.success(`Saved “${name.trim()}”. Insert it from Add → Saved sections, on any screen.`);
          setName("");
        } catch (err) {
          toast.error(c.errorText(err));
        }
      }}
    >
      <Input aria-label="Section name" placeholder="Save as a section…" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
      <Button size="sm" type="submit" disabled={!name.trim()}>Save</Button>
    </form>
  );
}

const ROOT_SETTINGS: Record<string, Array<{ attr: string; label: string; kind: "bool" | "field" | "text" | "choice"; choices?: string[]; types?: string[] }>> = {
  list: [
    { attr: "editable", label: "Edit rows in place", kind: "choice", choices: ["", "top", "bottom"] },
    { attr: "default_group_by", label: "Group rows by", kind: "field", types: ["char", "selection", "many2one", "boolean", "date", "datetime"] },
    { attr: "default_order", label: "Sort by (e.g. date desc)", kind: "text" },
    { attr: "limit", label: "Rows per page", kind: "text" },
    { attr: "create", label: "Allow creating", kind: "bool" },
    { attr: "delete", label: "Allow deleting", kind: "bool" },
    { attr: "multi_edit", label: "Edit several rows at once", kind: "bool" },
  ],
  kanban: [
    { attr: "default_group_by", label: "Columns by", kind: "field", types: ["selection", "many2one", "char", "boolean"] },
    { attr: "default_order", label: "Sort by", kind: "text" },
    { attr: "quick_create", label: "Quick create", kind: "bool" },
    { attr: "highlight_color", label: "Card colour from (Odoo 18+)", kind: "field", types: ["integer"] },
  ],
  calendar: [
    { attr: "date_start", label: "Starts", kind: "field", types: ["date", "datetime"] },
    { attr: "date_stop", label: "Ends", kind: "field", types: ["date", "datetime"] },
    { attr: "color", label: "Colour by", kind: "field", types: ["many2one", "selection", "integer"] },
    { attr: "mode", label: "Opens on", kind: "choice", choices: ["day", "week", "month", "year"] },
    { attr: "quick_create", label: "Quick create", kind: "bool" },
  ],
  form: [
    { attr: "create", label: "Allow creating", kind: "bool" },
    { attr: "edit", label: "Allow editing", kind: "bool" },
    { attr: "delete", label: "Allow deleting", kind: "bool" },
  ],
};

/** Whole-screen settings plus the list/card/search designers' adds. */
export function ScreenSettings({ root, ...c }: Common & { root: EngineNode }) {
  const tag = root.tag === "tree" ? "list" : root.tag;
  const settings = ROOT_SETTINGS[tag] ?? [];
  const fieldNames = (types?: string[]) =>
    Object.entries(c.fields)
      .filter(([, m]) => !types || types.includes(m.type ?? ""))
      .sort((a, b) => (a[1].string ?? a[0]).localeCompare(b[1].string ?? b[0]));
  const set = (attr: string, value: string) => c.onOp({ op: "set_attr", node: root.id, attr, value });
  const [label, setLabel] = useState("");
  const [deco, setDeco] = useState("danger");
  const [cardKind, setCardKind] = useState("field");
  const [cardField, setCardField] = useState("");
  const [cardColour, setCardColour] = useState("danger");

  return (
    <section className={styles.section} aria-label="Screen settings" data-testid="vd-screen-settings">
      <h3 className={styles.sectionTitle}>Screen settings</h3>
      {settings.map((s) => (
        <label key={s.attr} className={s.kind === "bool" ? styles.check : styles.fieldLabel}>
          {s.kind === "bool" ? (
            <>
              <input type="checkbox" checked={!["0", "false", "False"].includes(root.attrs[s.attr] ?? "1")} onChange={(e) => set(s.attr, e.target.checked ? "1" : "0")} /> {s.label}
            </>
          ) : (
            <>
              {s.label}
              {s.kind === "field" ? (
                <select className={styles.select} value={root.attrs[s.attr] ?? ""} onChange={(e) => set(s.attr, e.target.value)}>
                  <option value="">None</option>
                  {fieldNames(s.types).map(([n, m]) => <option key={n} value={n}>{m.string ?? n}</option>)}
                </select>
              ) : s.kind === "choice" ? (
                <select className={styles.select} value={root.attrs[s.attr] ?? ""} onChange={(e) => set(s.attr, e.target.value)}>
                  {(s.choices ?? []).map((v) => <option key={v} value={v}>{v || "No"}</option>)}
                </select>
              ) : (
                <Input defaultValue={root.attrs[s.attr] ?? ""} onBlur={(e) => e.target.value !== (root.attrs[s.attr] ?? "") && set(s.attr, e.target.value)} />
              )}
            </>
          )}
        </label>
      ))}

      {tag === "list" ? (
        <>
          <h3 className={styles.sectionTitle}>Row colours</h3>
          <select className={styles.select} aria-label="Colour" value={deco} onChange={(e) => setDeco(e.target.value)}>
            {DECORATIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <OneRule fields={c.fields} label="Colour rows" onPick={(condition) => c.onOp({ op: "set_decoration", node: root.id, style: deco, condition })} />
        </>
      ) : null}

      {tag === "kanban" ? (
        <>
          <h3 className={styles.sectionTitle}>Add to the card</h3>
          <div className={styles.row}>
            <select className={styles.select} aria-label="Card item" value={cardKind} onChange={(e) => setCardKind(e.target.value)}>
              <option value="field">Field</option>
              <option value="tags">Tags</option>
              <option value="progress">Progress bar</option>
              <option value="cover">Cover image</option>
              <option value="badge">Badge</option>
            </select>
            <select className={styles.select} aria-label="From field" value={cardField} onChange={(e) => setCardField(e.target.value)}>
              <option value="">Field…</option>
              {fieldNames().map(([n, m]) => <option key={n} value={n}>{m.string ?? n}</option>)}
            </select>
            <Button size="sm" disabled={!cardField} onClick={() => c.onOp({ op: "kanban_add", kind: cardKind, field: cardField, props: { field: cardField } })}>Add</Button>
          </div>
          <h3 className={styles.sectionTitle}>Colour flag</h3>
          <select className={styles.select} aria-label="Flag colour" value={cardColour} onChange={(e) => setCardColour(e.target.value)}>
            {CARD_COLOURS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <OneRule fields={c.fields} label="Colour flag when" onPick={(condition) => c.onOp({ op: "kanban_add", kind: "colour", condition, props: { style: cardColour } })} />
        </>
      ) : null}

      {tag === "search" ? (
        <>
          <h3 className={styles.sectionTitle}>Filters and grouping</h3>
          <Input aria-label="Name" placeholder="Name shown in the search menu" value={label} onChange={(e) => setLabel(e.target.value)} maxLength={80} />
          <OneRule fields={c.fields} label="Add filter" onPick={(condition) => label.trim() && c.onOp({ op: "search_add_filter", label: label.trim(), condition })} />
          <div className={styles.row}>
            <select className={styles.select} aria-label="Group by field" defaultValue="" onChange={(e) => {
              const f = e.target.value;
              if (f) c.onOp({ op: "search_add_groupby", field: f, label: label.trim() || c.fields[f]?.string || f });
              e.target.value = "";
            }}>
              <option value="">Add “Group by”…</option>
              {fieldNames(["char", "selection", "many2one", "boolean", "date", "datetime"]).map(([n, m]) => <option key={n} value={n}>{m.string ?? n}</option>)}
            </select>
            <select className={styles.select} aria-label="Search in field" defaultValue="" onChange={(e) => {
              const f = e.target.value;
              if (f) c.onOp({ op: "search_add_field", field: f });
              e.target.value = "";
            }}>
              <option value="">Search in field…</option>
              {fieldNames(["char", "many2one", "text", "selection"]).map(([n, m]) => <option key={n} value={n}>{m.string ?? n}</option>)}
            </select>
          </div>
        </>
      ) : null}
    </section>
  );
}
