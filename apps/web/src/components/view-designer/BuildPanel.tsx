"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";
import type { EngineNode, EngineOp, EngineViewType } from "@/lib/api/view-engine";
import type { FieldSpec, LibraryItem, LibraryOut, RelatedChoice, SectionItem, SmartOption } from "@/lib/api/view-engine-2b";
import { placeElement, placeField } from "@/lib/viewDesigner2b";
import { Note } from "../view-designer/Note";
import styles from "./ViewDesigner.module.css";
import { Term } from "@/components/ui/Term";

type Props = {
  connectionId: string;
  model: string;
  viewType: EngineViewType;
  viewId: number | null;
  ops: EngineOp[];
  tree: EngineNode;
  selected: EngineNode | null;
  onOps: (ops: EngineOp[], summary: string) => void;
  /** After a field is created in Odoo the screen reloads its field list. */
  onFieldsChanged: () => void;
  errorText: (err: unknown) => string;
};

/** "Add": Odoo Studio's component set for this version, new fields, related fields, saved sections. */
export function BuildPanel({ connectionId, model, viewType, viewId, ops, tree, selected, onOps, onFieldsChanged, errorText }: Props) {
  const [lib, setLib] = useState<LibraryOut | null>(null);
  const [query, setQuery] = useState("");
  const [creating, setCreating] = useState<string | null>(null);
  const [related, setRelated] = useState<RelatedChoice[] | null>(null);
  const [sections, setSections] = useState<SectionItem[]>([]);
  const [smartOpen, setSmartOpen] = useState(false);

  const load = useCallback(async () => {
    try {
      setLib(await api.library(connectionId, { model, view_type: viewType, view_id: viewId, ops }));
    } catch (err) {
      toast.error(errorText(err));
    }
    // Pending ops change what's on screen; reload only when the screen changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connectionId, model, viewType, viewId]);

  useEffect(() => {
    void load();
    api.sectionList(connectionId, model).then((o) => setSections(o.sections)).catch(() => setSections([]));
  }, [load, connectionId, model]);

  const add = (op: EngineOp | null, summary: string, err?: string) => {
    if (!op) {
      if (err) toast(err);
      return;
    }
    onOps([op], summary);
  };

  const addField = (field: string, label: string, widget?: string) => {
    const p = placeField(tree, selected);
    if ("error" in p) return add(null, "", p.error);
    add({ op: "insert_field", field, target: p.target, position: p.position, ...(widget ? { widget } : {}) }, `Add ${label}`);
  };

  const addElement = (item: LibraryItem, props: Record<string, unknown> = {}) => {
    const p = placeElement(item.kind, tree, selected);
    if ("error" in p) return add(null, "", p.error);
    add({ op: "insert_element", element: item.kind, target: p.target, position: p.position, props: { ...item.props, ...props } }, `Add ${item.label.toLowerCase()}`);
  };

  const q = query.trim().toLowerCase();
  const existing = useMemo(
    () => (lib?.existing_fields ?? []).filter((f) => !f.on_screen && (!q || f.label.toLowerCase().includes(q) || f.name.includes(q))).slice(0, 60),
    [lib, q],
  );

  if (!lib) return <p className={styles.panelBody + " " + styles.muted}>Loading the component library…</p>;
  const isForm = lib.root_tag === "form";

  return (
    <div className={styles.panelBody} data-testid="vd-build">
      <p className={styles.muted}>
        Odoo {lib.major}. {selected ? `New items go next to or inside “${selected.label}”.` : "Select a group or tab first to choose where new items go."}
      </p>

      {isForm || ["list", "tree", "kanban"].includes(lib.root_tag) ? (
        <section className={styles.section} aria-labelledby="vd-new-field">
          <h3 id="vd-new-field" className={styles.sectionTitle}>New field</h3>
          <div className={styles.chipList}>
            {lib.field_types.map((t) => (
              <button key={t.key} type="button" className={styles.chip} onClick={() => setCreating(t.key)} data-testid={`vd-newtype-${t.key}`}>
                {t.label}
              </button>
            ))}
          </div>
          {creating ? (
            <NewFieldForm
              connectionId={connectionId}
              model={model}
              typeKey={creating}
              typeLabel={lib.field_types.find((t) => t.key === creating)?.label ?? creating}
              related={related}
              loadRelated={() => api.relatedChoices(connectionId, model).then((o) => setRelated(o.choices))}
              onCancel={() => setCreating(null)}
              onUseExisting={(name, label) => {
                setCreating(null);
                addField(name, label);
              }}
              onCreated={(name, label, widget) => {
                setCreating(null);
                onFieldsChanged();
                // The field exists in Odoo now; put it on the screen as a pending change.
                window.setTimeout(() => addField(name, label, widget ?? undefined), 600);
              }}
              errorText={errorText}
            />
          ) : null}
        </section>
      ) : null}

      <section className={styles.section} aria-labelledby="vd-existing">
        <h3 id="vd-existing" className={styles.sectionTitle}>Existing fields</h3>
        <Input aria-label="Search fields" placeholder="Search fields…" value={query} onChange={(e) => setQuery(e.target.value)} />
        <ul className={styles.fieldList}>
          {existing.map((f) => (
            <li key={f.name} className={styles.fieldRow}>
              <span>
                {f.label} <span className={styles.muted}>{f.type}</span>
              </span>
              {f.widgets.length > 1 ? (
                <select
                  className={styles.select}
                  aria-label={`Show ${f.label} as`}
                  defaultValue=""
                  onChange={(e) => {
                    if (e.target.value !== "-") addField(f.name, f.label, e.target.value || undefined);
                    e.target.value = "-";
                  }}
                >
                  <option value="-">Add as…</option>
                  <option value="">Default</option>
                  {f.widgets.map((w) => (
                    <option key={w.name} value={w.name}>{w.label}</option>
                  ))}
                </select>
              ) : (
                <Button size="sm" variant="ghost" onClick={() => addField(f.name, f.label)}>Add</Button>
              )}
            </li>
          ))}
        </ul>
      </section>

      {lib.layout.length ? (
        <section className={styles.section} aria-labelledby="vd-layout">
          <h3 id="vd-layout" className={styles.sectionTitle}>Layout</h3>
          <div className={styles.chipList}>
            {lib.layout.map((item) => (
              <button key={item.kind + item.label} type="button" className={styles.chip} onClick={() => addElement(item)} data-testid={`vd-el-${item.kind}`}>
                {item.label}
              </button>
            ))}
          </div>
        </section>
      ) : null}

      {lib.buttons.length ? (
        <section className={styles.section} aria-labelledby="vd-buttons">
          <h3 id="vd-buttons" className={styles.sectionTitle}>Buttons</h3>
          <div className={styles.chipList}>
            {lib.buttons.map((item) =>
              item.kind === "smart_button" ? (
                <button key={item.kind} type="button" className={styles.chip} onClick={() => setSmartOpen(true)}>{item.label}…</button>
              ) : item.kind === "statusbar" ? (
                <StatusbarChip key={item.kind} lib={lib} onAdd={(field) => addElement(item, { field })} />
              ) : (
                <button key={item.kind} type="button" className={styles.chip} onClick={() => {
                  const label = window.prompt("Button text", item.label) ?? "";
                  if (!label.trim()) return;
                  const method = item.kind === "link_button" ? undefined : window.prompt("Which action should it run? (an action the record type already has)") ?? "";
                  addElement(item, { label: label.trim(), ...(method ? { method: method.trim() } : {}) });
                }}>
                  {item.label}
                </button>
              ),
            )}
          </div>
          {smartOpen ? (
            <SmartButtonForm
              connectionId={connectionId}
              model={model}
              onCancel={() => setSmartOpen(false)}
              onReady={(props, label) => {
                setSmartOpen(false);
                onFieldsChanged();
                window.setTimeout(() => addElement({ kind: "smart_button", label }, props), 600);
              }}
              errorText={errorText}
            />
          ) : null}
        </section>
      ) : null}

      {sections.length && isForm ? (
        <section className={styles.section} aria-labelledby="vd-sections">
          <h3 id="vd-sections" className={styles.sectionTitle}>Saved sections</h3>
          <ul className={styles.fieldList}>
            {sections.map((sec) => {
              const onScreenNow = new Set((lib.existing_fields ?? []).filter((f) => f.on_screen).map((f) => f.name));
              const already = sec.payload.fields.filter((f) => onScreenNow.has(f.name));
              return (
              <li key={sec.id} className={styles.fieldRow}>
                <span>
                  {sec.name} <span className={styles.muted}>{sec.payload.fields.length} fields{sec.fit && !sec.fit.fits ? `, ${sec.fit.missing.length} missing here` : ""}{already.length ? `, ${already.length} already on this screen (left out)` : ""}</span>
                </span>
                <span>
                  <Button size="sm" variant="ghost" onClick={() => {
                    const p = placeElement("group", tree, selected);
                    if ("error" in p) return toast(p.error);
                    const onScreen = new Set((lib.existing_fields ?? []).filter((f) => f.on_screen).map((f) => f.name));
                    const skip = sec.payload.fields.map((f) => f.name).filter((n) => onScreen.has(n) || sec.fit?.missing.some((m) => m.name === n));
                    if (skip.length === sec.payload.fields.length) return toast("Everything in that section is already on this screen.");
                    onOps([{ op: "insert_section", xml: sec.payload.xml, target: p.target, position: p.position, skip }], `Insert section ${sec.name}`);
                    if (skip.length) {
                      const labels = sec.payload.fields.filter((f) => skip.includes(f.name)).map((f) => f.label || f.name);
                      toast(`Left out ${labels.length === 1 ? "1 field" : `${labels.length} fields`} already on this screen or not on this record type: ${labels.join(", ")}.`);
                    }
                  }}>
                    Insert
                  </Button>
                  <Button size="sm" variant="ghost" aria-label={`Delete section ${sec.name}`} onClick={async () => {
                    await api.sectionDelete(connectionId, sec.id);
                    setSections((cur) => cur.filter((x) => x.id !== sec.id));
                  }}>
                    ×
                  </Button>
                </span>
              </li>
              );
            })}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

function StatusbarChip({ lib, onAdd }: { lib: LibraryOut; onAdd: (field: string) => void }) {
  const choices = lib.existing_fields.filter((f) => f.type === "selection" || f.type === "many2one");
  return (
    <select className={styles.select} aria-label="Status bar from field" defaultValue="" onChange={(e) => e.target.value && onAdd(e.target.value)}>
      <option value="">Status bar from…</option>
      {choices.map((f) => (
        <option key={f.name} value={f.name}>{f.label}</option>
      ))}
    </select>
  );
}

type NewFieldProps = {
  connectionId: string;
  model: string;
  typeKey: string;
  typeLabel: string;
  related: RelatedChoice[] | null;
  loadRelated: () => Promise<void>;
  onCancel: () => void;
  onUseExisting: (name: string, label: string) => void;
  onCreated: (name: string, label: string, widget: string | null) => void;
  errorText: (err: unknown) => string;
};

/** Inline field creation. Stock first: a similar existing field is offered before anything is made. */
function NewFieldForm({ connectionId, model, typeKey, typeLabel, related, loadRelated, onCancel, onUseExisting, onCreated, errorText }: NewFieldProps) {
  const [label, setLabel] = useState("");
  const [relation, setRelation] = useState("");
  const [inverse, setInverse] = useState("");
  const [inverseOptions, setInverseOptions] = useState<Array<{ name: string; label: string }>>([]);
  const [choices, setChoices] = useState("");
  const [path, setPath] = useState("");
  const [similar, setSimilar] = useState<Array<{ name: string; label: string }> | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (typeKey === "related" && !related) void loadRelated();
  }, [typeKey, related, loadRelated]);

  useEffect(() => {
    if (typeKey !== "lines" || !/^[a-z_][a-z0-9_.]+$/.test(relation)) return;
    api.inverseOptions(connectionId, model, relation).then((o) => setInverseOptions(o.options)).catch(() => setInverseOptions([]));
  }, [typeKey, relation, connectionId, model]);

  const submit = async (force = false) => {
    const spec: FieldSpec = { type: typeKey, label: label.trim() };
    if (["link", "tags", "lines"].includes(typeKey)) spec.relation = relation.trim();
    if (typeKey === "lines") spec.relation_field = inverse;
    if (typeKey === "choice") spec.choices = choices.split(/\n|,/).map((c) => c.trim()).filter(Boolean);
    if (typeKey === "related") spec.related = path;
    setBusy(true);
    try {
      const out = await api.fieldCreate(connectionId, model, spec, force);
      if (!out.created) {
        setSimilar(out.similar);
        return;
      }
      toast.success(`Created ${out.label} in Odoo`, {
        description: "It's added to the screen as a pending change.",
        action: { label: "Undo", onClick: () => void api.fieldDelete(connectionId, model, out.name) },
      });
      onCreated(out.name, out.label, out.widget);
    } catch (err) {
      toast.error(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className={styles.stack} onSubmit={(e) => { e.preventDefault(); void submit(); }} data-testid="vd-newfield-form">
      <h4 className={styles.sectionTitle}>New {typeLabel.toLowerCase()}</h4>
      {typeKey === "related" ? (
        <select className={styles.select} aria-label="Show a value from a linked record" value={path} onChange={(e) => {
          setPath(e.target.value);
          const item = related?.flatMap((r) => r.items).find((i) => i.path === e.target.value);
          if (item && !label) setLabel(item.label.split(" > ").pop() ?? "");
        }}>
          <option value="">Pick a value…</option>
          {(related ?? []).map((r) => (
            <optgroup key={r.field} label={r.label}>
              {r.items.map((i) => <option key={i.path} value={i.path}>{i.label}</option>)}
            </optgroup>
          ))}
        </select>
      ) : null}
      <label className={styles.fieldLabel}>
        Label
        <Input value={label} onChange={(e) => setLabel(e.target.value)} required maxLength={80} />
      </label>
      {["link", "tags", "lines"].includes(typeKey) ? (
        <label className={styles.fieldLabel}>
          Linked <Term tech="ir.model">record type</Term> (e.g. res.partner)
          <Input value={relation} onChange={(e) => setRelation(e.target.value)} required spellCheck={false} />
        </label>
      ) : null}
      {typeKey === "lines" ? (
        <select className={styles.select} aria-label="Field on the lines that points back here" value={inverse} onChange={(e) => setInverse(e.target.value)} required>
          <option value="">Which field on the lines points back here?</option>
          {inverseOptions.map((o) => <option key={o.name} value={o.name}>{o.label}</option>)}
        </select>
      ) : null}
      {typeKey === "choice" ? (
        <label className={styles.fieldLabel}>
          Choices (one per line)
          <textarea className={styles.textarea} value={choices} onChange={(e) => setChoices(e.target.value)} rows={4} required />
        </label>
      ) : null}
      {similar ? (
        <Note tone="danger" as="div" role="alert">
          <p>A similar field already exists. Odoo works best when fields are reused.</p>
          {similar.map((f) => (
            <Button key={f.name} size="sm" onClick={() => onUseExisting(f.name, f.label)}>Use {f.label}</Button>
          ))}
          <Button size="sm" variant="ghost" onClick={() => void submit(true)}>Create a new field anyway</Button>
        </Note>
      ) : null}
      <div className={styles.row}>
        <Button size="sm" variant="primary" type="submit" loading={busy}>Create and add</Button>
        <Button size="sm" variant="ghost" type="button" onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  );
}

function SmartButtonForm({
  connectionId,
  model,
  onCancel,
  onReady,
  errorText,
}: {
  connectionId: string;
  model: string;
  onCancel: () => void;
  onReady: (props: Record<string, unknown>, label: string) => void;
  errorText: (err: unknown) => string;
}) {
  const [options, setOptions] = useState<SmartOption[]>([]);
  const [pick, setPick] = useState("");
  const [label, setLabel] = useState("");
  const [count, setCount] = useState(true);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api.smartOptions(connectionId, model).then((o) => setOptions(o.options)).catch(() => setOptions([]));
  }, [connectionId, model]);
  const chosen = options.find((o) => `${o.relation}|${o.field}` === pick);
  return (
    <form
      className={styles.stack}
      onSubmit={async (e) => {
        e.preventDefault();
        if (!chosen) return;
        setBusy(true);
        try {
          const out = await api.smartAction(connectionId, { model, relation: chosen.relation, field: chosen.field, label: label.trim(), with_count: count });
          toast.success("The list the button opens was made in Odoo", {
            action: { label: "Undo", onClick: () => void api.smartUndo(connectionId, { action_id: out.action_id, count_field_id: out.count_field_id }) },
          });
          onReady({ label: label.trim(), action_id: out.action_id, ...(out.count_field ? { count_field: out.count_field } : {}) }, label.trim());
        } catch (err) {
          toast.error(errorText(err));
        } finally {
          setBusy(false);
        }
      }}
    >
      <h4 className={styles.sectionTitle}>Smart button</h4>
      <select className={styles.select} aria-label="Opens" value={pick} onChange={(e) => {
        setPick(e.target.value);
        const o = options.find((x) => `${x.relation}|${x.field}` === e.target.value);
        if (o && !label) setLabel(o.relation_label ?? o.relation);
      }} required>
        <option value="">Opens the list of…</option>
        {options.map((o) => (
          <option key={`${o.relation}|${o.field}`} value={`${o.relation}|${o.field}`}>
            {o.relation_label ?? o.relation} (by {o.field_label ?? o.field})
          </option>
        ))}
      </select>
      <label className={styles.fieldLabel}>
        Button text
        <Input value={label} onChange={(e) => setLabel(e.target.value)} required maxLength={80} />
      </label>
      <label className={styles.check}>
        <input type="checkbox" checked={count} onChange={(e) => setCount(e.target.checked)} /> Show how many there are
      </label>
      <div className={styles.row}>
        <Button size="sm" variant="primary" type="submit" loading={busy} disabled={!chosen}>Add smart button</Button>
        <Button size="sm" variant="ghost" type="button" onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  );
}
