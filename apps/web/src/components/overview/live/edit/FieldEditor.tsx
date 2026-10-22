"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { api, type SnapshotModelDetail } from "@/lib/api";
import { parseOptions, selectionLiteral, slug } from "./gates";
import { PreviewApply, errorText, type Phase } from "./PreviewApply";

type Field = SnapshotModelDetail["fields"][number];

const TYPES = [
  ["char", "Short text"], ["text", "Long text"], ["integer", "Whole number"], ["float", "Decimal number"],
  ["monetary", "Amount"], ["boolean", "Yes / no"], ["date", "Date"], ["datetime", "Date and time"],
  ["selection", "Choice list"], ["many2one", "Link to another record"],
] as const;
const TYPE_LABEL: Record<string, string> = Object.fromEntries(TYPES);

const input =
  "w-full rounded-md border border-border-subtle bg-surface-raised px-2.5 py-1.5 text-ui-body text-ink focus:outline-none focus:ring-2 focus:ring-accent";

/** Add an x_ field (any model) or edit a custom field's label / required / help / options. */
export function FieldEditor({ connectionId, model, modelLabel, field, onDone, onCancel }: {
  connectionId: string;
  model: string;
  modelLabel: string;
  field?: Field;
  onDone: () => void;
  onCancel: () => void;
}) {
  const editing = !!field;
  const [label, setLabel] = useState(field?.string ?? "");
  const [name, setName] = useState(field?.name ?? "");
  const [type, setType] = useState<string>(field?.type ?? "char");
  const [relation, setRelation] = useState(field?.relation ?? "");
  const [required, setRequired] = useState(field?.required ?? false);
  const [help, setHelp] = useState(field?.help ?? "");
  const [options, setOptions] = useState((field?.selection ?? []).map((v) => `${v}: ${v}`).join("\n"));
  const [phase, setPhase] = useState<Phase>({ kind: "edit" });

  const tech = editing ? name : name || (label ? `x_${slug(label)}` : "");
  const opts = parseOptions(options);
  const problems = [
    !label.trim() ? "Give the field a label." : "",
    !editing && !/^x_[a-z0-9_]+$/.test(tech) ? "The technical name must start with x_ and use a-z, 0-9 and _." : "",
    type === "selection" && opts.length === 0 ? "Add at least one choice." : "",
    type === "many2one" && !relation.trim() ? "Say which model it links to, e.g. res.partner." : "",
  ].filter(Boolean);

  const changes = editing
    ? [
        label !== field!.string ? `Rename “${field!.string}” to “${label}”` : "",
        required !== field!.required ? (required ? "Make it required" : "Make it optional") : "",
        help !== (field!.help ?? "") ? (help ? `Set the help text to “${help}”` : "Remove the help text") : "",
        type === "selection" && options !== (field!.selection ?? []).map((v) => `${v}: ${v}`).join("\n")
          ? `Set the choices to ${opts.map((o) => o.label).join(", ")}` : "",
      ].filter(Boolean)
    : [
        `Add “${label}” (${TYPE_LABEL[type] ?? type}) to ${modelLabel}, as ${tech}`,
        required ? "Required on every record" : "",
        type === "selection" ? `Choices: ${opts.map((o) => o.label).join(", ")}` : "",
        type === "many2one" ? `Links to ${relation}` : "",
        help ? `Help text: “${help}”` : "",
        "Shown on the form, so people can fill it in",
      ].filter(Boolean);

  async function apply() {
    setPhase({ kind: "applying" });
    try {
      if (editing) {
        if (field!.id == null) throw new Error("This field can't be edited from here.");
        await api.updateField(connectionId, field!.id, {
          field_description: label,
          required,
          help: help || null,
          ...(type === "selection" ? { selection: selectionLiteral(opts) } : {}),
        });
      } else {
        await api.createField(connectionId, {
          model, name: tech, field_description: label, ttype: type, required,
          help: help || null,
          relation: type === "many2one" ? relation.trim() : null,
          selection: type === "selection" ? opts : null,
          inject_into_views: true, inject_strategy: "inherit",
        });
      }
      onDone();
    } catch (err) {
      setPhase({ kind: "error", message: errorText(err) });
    }
  }

  if (phase.kind !== "edit") {
    return (
      <PreviewApply
        title={editing ? `Change ${field!.string || field!.name}` : `Add a field to ${modelLabel}`}
        changes={changes.length ? changes : ["No changes"]}
        phase={phase}
        onBack={() => setPhase({ kind: "edit" })}
        onApply={() => void apply()}
      />
    );
  }
  return (
    <form
      className="space-y-2.5 rounded-md border border-border-subtle p-3"
      data-testid="field-editor"
      onSubmit={(e) => { e.preventDefault(); if (!problems.length && changes.length) setPhase({ kind: "preview" }); }}
    >
      <div className="grid gap-2.5 sm:grid-cols-2">
        <label className="space-y-1 text-ui-label text-muted">Label
          <input className={input} value={label} onChange={(e) => setLabel(e.target.value)} autoFocus />
        </label>
        {!editing ? (
          <label className="space-y-1 text-ui-label text-muted">Technical name
            <input className={`${input} font-mono`} value={tech} spellCheck={false}
              onChange={(e) => setName(e.target.value)} />
          </label>
        ) : null}
        {!editing ? (
          <label className="space-y-1 text-ui-label text-muted">Type
            <select className={input} value={type} onChange={(e) => setType(e.target.value)}>
              {TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
        ) : null}
        {!editing && type === "many2one" ? (
          <label className="space-y-1 text-ui-label text-muted">Links to (model)
            <input className={`${input} font-mono`} value={relation} spellCheck={false}
              placeholder="res.partner" onChange={(e) => setRelation(e.target.value)} />
          </label>
        ) : null}
      </div>
      {type === "selection" ? (
        <label className="block space-y-1 text-ui-label text-muted">Choices, one per line (value: Label)
          <textarea className={`${input} min-h-20 font-mono`} value={options} onChange={(e) => setOptions(e.target.value)} />
        </label>
      ) : null}
      <label className="block space-y-1 text-ui-label text-muted">Help text (optional)
        <input className={input} value={help} onChange={(e) => setHelp(e.target.value)} />
      </label>
      <label className="flex items-center gap-2 text-ui-body text-ink">
        <input type="checkbox" checked={required} onChange={(e) => setRequired(e.target.checked)} /> Required
      </label>
      {problems.length ? <p className="text-ui-meta text-status-warning-strong" data-testid="field-problems">{problems[0]}</p> : null}
      <div className="flex gap-2">
        <Button type="submit" variant="secondary" size="sm" disabled={!!problems.length || !changes.length}>Review change</Button>
        <Button type="button" variant="ghost" size="sm" onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  );
}
