"use client";

import { FormEvent } from "react";
import { ExplainThisButton } from "@/components/expert/ExplainThisButton";
import { ModelTierInline } from "@/components/ModelTierInline";
import {
  SelectionEditor,
  selectionRowsToString,
  type SelectionRow,
} from "@/components/SelectionEditor";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Card } from "@/components/ui/layout-primitives";
import { Disclosure } from "@/components/ui/Disclosure";
import { Input } from "@/components/ui/Input";
import type { Connection, RelatedPathOption } from "@/lib/api";
import type { WidgetOption } from "@/lib/widgetCatalog";
import {
  FIELD_TYPE_GROUPS,
  fieldTypeLabel,
  needsCurrency,
  needsOnDelete,
  needsRelation,
  needsSelection,
  slugifyTechnical,
  type FieldComposerForm,
} from "@/lib/builderForm";
import {
  connectionSupports,
  connectionUnsupportedReason,
  currencyFieldSupported,
  currencyFieldUnsupportedReason,
  injectStrategyCapabilityId,
} from "@/lib/capabilities";

type FieldComposerProps = {
  connectionId: string;
  connection: Connection | null;
  form: FieldComposerForm;
  mode: "create" | "edit";
  onChange: (patch: Partial<FieldComposerForm>) => void;
  onSubmit: (e: FormEvent) => void;
  busy?: boolean;
  widgetOptions: WidgetOption[];
  relatedPaths: RelatedPathOption[];
};

export function FieldComposer({
  connectionId,
  connection,
  form,
  mode,
  onChange,
  onSubmit,
  busy,
  widgetOptions,
  relatedPaths,
}: FieldComposerProps) {
  const relation = needsRelation(form.ttype);
  const onDelete = needsOnDelete(form.ttype);
  const selection = needsSelection(form.ttype);
  const currency = needsCurrency(form.ttype);
  const hasRelatedPath = Boolean(form.related.trim());
  const injectCap = injectStrategyCapabilityId(form.inject_strategy);
  const canInjectStrategy = connectionSupports(connection, injectCap);
  const editing = mode === "edit";
  const submitLabel = busy
    ? "Working…"
    : editing
      ? "Save field"
      : "Create field";

  return (
    <form onSubmit={onSubmit} className="space-y-4" data-testid="builder-field-form">
      <Card className="space-y-4 p-5">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
            {editing ? "Edit field" : "New field"}
          </p>
          <h2 className="text-base font-semibold text-ink">
            {editing ? form.name : "Add a field"}
          </h2>
          <p className="mt-1 text-sm text-muted">
            {editing
              ? "Label, help, required, and readonly can change. Type and technical name stay fixed."
              : "Custom columns use an x_ name. Injecting into views is optional and reversible via inherit."}
          </p>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="builder-field-model" className="block text-sm font-medium text-ink">
            Target model
          </label>
          <input
            id="builder-field-model"
            required
            disabled={editing}
            value={form.model}
            onChange={(e) => onChange({ model: e.target.value })}
            className="h-9 w-full rounded-md border border-border-subtle bg-surface px-3 font-mono text-sm text-ink outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 disabled:opacity-60"
            placeholder="res.partner or x_…"
            data-testid="builder-field-model"
          />
          <ModelTierInline connectionId={connectionId} model={form.model} />
        </div>

        <Input
          label="Label"
          required
          value={form.field_description}
          onChange={(e) => {
            const field_description = e.target.value;
            onChange(
              editing
                ? { field_description }
                : { field_description, name: slugifyTechnical(field_description) },
            );
          }}
          placeholder="Customer note"
        />

        <Input
          label="Technical name"
          required
          value={form.name}
          disabled={editing}
          onChange={(e) => onChange({ name: e.target.value })}
          className="font-mono"
          pattern="x_[A-Za-z0-9_]+"
          hint={editing ? "Renaming a column is not supported from this screen." : undefined}
        />

        <div className="space-y-1.5">
          <label htmlFor="builder-field-ttype" className="flex items-center gap-1 text-sm font-medium text-ink">
            Type
            <ExplainThisButton
              question={`Explain many2one vs many2many vs one2many for a new field on ${form.model}`}
              label="Explain field types"
            />
          </label>
          <select
            id="builder-field-ttype"
            data-testid="builder-field-ttype"
            disabled={editing}
            value={form.ttype}
            onChange={(e) => onChange({ ttype: e.target.value })}
            className="h-9 w-full rounded-md border border-border-subtle bg-surface px-3 text-sm text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 disabled:opacity-60"
          >
            {FIELD_TYPE_GROUPS.map((group) => (
              <optgroup key={group.id} label={group.label}>
                {group.types.map((t) => (
                  <option key={t} value={t}>
                    {fieldTypeLabel(t)}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>

        {relation ? (
          <Input
            label="Relation model"
            required={!editing}
            disabled={editing}
            value={form.relation}
            onChange={(e) => onChange({ relation: e.target.value })}
            className="font-mono"
            placeholder="res.partner"
          />
        ) : null}

        {form.ttype === "one2many" ? (
          <Input
            label="Relation field"
            required={!editing}
            disabled={editing}
            value={form.relation_field}
            onChange={(e) => onChange({ relation_field: e.target.value })}
            className="font-mono"
            placeholder="x_parent_id"
            hint="Many2one field on the related model that points back here."
          />
        ) : null}

        {onDelete && !editing ? (
          <div className="space-y-1.5">
            <label htmlFor="builder-on-delete" className="block text-sm font-medium text-ink">
              On delete
            </label>
            <select
              id="builder-on-delete"
              value={form.on_delete}
              onChange={(e) =>
                onChange({
                  on_delete: e.target.value as FieldComposerForm["on_delete"],
                })
              }
              className="h-9 w-full rounded-md border border-border-subtle bg-surface px-3 text-sm text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
            >
              <option value="restrict">Restrict</option>
              <option value="cascade">Cascade</option>
              <option value="set null">Set null</option>
            </select>
            <p className="text-xs text-muted">
              Required many2one cannot use set null on Odoo 19 — prefer restrict.
            </p>
          </div>
        ) : null}

        {selection ? (
          <div className="space-y-1.5">
            <p className="text-sm font-medium text-ink">Selection options</p>
            <SelectionEditor
              value={form.selectionRows}
              onChange={(selectionRows: SelectionRow[]) => onChange({ selectionRows })}
            />
            <p className="text-xs text-muted">
              Serialized:{" "}
              <code className="text-muted">{selectionRowsToString(form.selectionRows)}</code>
            </p>
          </div>
        ) : null}

        {currency ? (
          <div className="space-y-2">
            <Input
              label="Currency field"
              value={form.currency_field}
              onChange={(e) => onChange({ currency_field: e.target.value })}
              className="font-mono"
              placeholder="currency_id"
              disabled={editing || !currencyFieldSupported(connection)}
            />
            {!currencyFieldSupported(connection) ? (
              <Callout variant="warning" title="Currency field unavailable" testId="builder-currency-gate">
                {currencyFieldUnsupportedReason(connection)}
              </Callout>
            ) : null}
          </div>
        ) : null}

        <Input
          label="Help"
          value={form.help}
          onChange={(e) => onChange({ help: e.target.value })}
          placeholder="Shown as a tooltip on the field"
        />

        <div className="flex flex-wrap gap-4 text-sm">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={form.required}
              onChange={(e) => onChange({ required: e.target.checked })}
            />
            Required
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={form.readonly || hasRelatedPath}
              disabled={hasRelatedPath}
              onChange={(e) => onChange({ readonly: e.target.checked })}
            />
            Readonly
          </label>
          {editing ? (
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={form.tracking}
                onChange={(e) => onChange({ tracking: e.target.checked })}
              />
              Track changes
            </label>
          ) : null}
        </div>

        {!editing ? (
          <Disclosure title="Related path, widget, and view inject" testId="builder-field-advanced">
            <div className="space-y-4">
              <div className="space-y-1.5">
                <label htmlFor="builder-related" className="block text-sm font-medium text-ink">
                  Related path
                </label>
                {relatedPaths.length > 0 ? (
                  <select
                    id="builder-related"
                    value={form.related}
                    onChange={(e) => onChange({ related: e.target.value })}
                    className="h-9 w-full rounded-md border border-border-subtle bg-surface px-3 font-mono text-sm text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                  >
                    <option value="">None</option>
                    {relatedPaths.map((p) => (
                      <option key={p.path} value={p.path}>
                        {p.label} ({p.path})
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    id="builder-related"
                    value={form.related}
                    onChange={(e) => onChange({ related: e.target.value })}
                    className="h-9 w-full rounded-md border border-border-subtle bg-surface px-3 font-mono text-sm text-ink outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                    placeholder="partner_id.country_id"
                  />
                )}
                <p className="text-xs text-muted">
                  When set, Odoo stores a readonly related field using the type above. There is no
                  ttype=related.
                </p>
              </div>

              {widgetOptions.length > 0 ? (
                <div className="space-y-1.5">
                  <label htmlFor="builder-widget" className="block text-sm font-medium text-ink">
                    Form widget hint
                  </label>
                  <select
                    id="builder-widget"
                    value={form.view_widget}
                    onChange={(e) => onChange({ view_widget: e.target.value })}
                    className="h-9 w-full rounded-md border border-border-subtle bg-surface px-3 text-sm text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                  >
                    <option value="">Default</option>
                    {widgetOptions.map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.label}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-muted">
                    When injecting into form views, sets widget on the field node.
                  </p>
                </div>
              ) : null}

              <label
                className="flex items-start gap-2 text-sm"
                title={connectionUnsupportedReason(connection, injectCap) ?? undefined}
              >
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={form.inject_into_views && canInjectStrategy}
                  disabled={!canInjectStrategy}
                  onChange={(e) => onChange({ inject_into_views: e.target.checked })}
                  data-testid="builder-inject-views"
                />
                <span>
                  <span className="font-medium text-ink">Inject into form, list, and search</span>
                  <span className="mt-0.5 block text-xs text-muted">
                    Adds the column to views. Hiding later is a View Designer change — it does not
                    drop the column.
                  </span>
                </span>
              </label>

              <div className="space-y-1.5">
                <label htmlFor="builder-inject-strategy" className="block text-sm font-medium text-ink">
                  Inject strategy
                </label>
                <select
                  id="builder-inject-strategy"
                  value={form.inject_strategy}
                  onChange={(e) =>
                    onChange({
                      inject_strategy: e.target.value as FieldComposerForm["inject_strategy"],
                    })
                  }
                  className="h-9 w-full rounded-md border border-border-subtle bg-surface px-3 text-sm text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                >
                  <option
                    value="inherit"
                    disabled={!connectionSupports(connection, "view_inject_inherit")}
                  >
                    Inherit xpath child
                    {!connectionSupports(connection, "view_inject_inherit") ? " — unavailable" : ""}
                  </option>
                  <option
                    value="mutate"
                    disabled={!connectionSupports(connection, "view_inject_mutate")}
                  >
                    Mutate parent arch
                    {!connectionSupports(connection, "view_inject_mutate") ? " — unavailable" : ""}
                  </option>
                </select>
              </div>
              {!canInjectStrategy ? (
                <Callout variant="warning" title="Inject unavailable" testId="builder-inject-gate">
                  {connectionUnsupportedReason(connection, injectCap)}
                </Callout>
              ) : null}
              {form.inject_strategy === "mutate" &&
              connectionSupports(connection, "view_inject_mutate") ? (
                <Callout variant="warning" title="Mutate overwrites parent view arch">
                  Requires advanced confirm on create. Prefer inherit for module upgrades.
                </Callout>
              ) : null}
            </div>
          </Disclosure>
        ) : (
          <Callout variant="info" title="Removing this field">
            Hide it in View Designer to drop it from a layout. Deprecate or hard-delete from the
            field list to change the model itself.
          </Callout>
        )}

        <Button type="submit" variant="primary" disabled={busy} data-testid="builder-submit-field">
          {submitLabel}
        </Button>
      </Card>
    </form>
  );
}
