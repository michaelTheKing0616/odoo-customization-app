"use client";

import { useEffect, useState } from "react";
import { DomainBuilder } from "@/components/DomainBuilder";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Combobox } from "@/components/ui/Combobox";
import { Disclosure } from "@/components/ui/Disclosure";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { Tooltip } from "@/components/ui/Tooltip";
import { HelpCircle, X } from "@/components/ui/icons";
import type { FieldRow, GroupRow, RelatedPathOption } from "@/lib/api";
import { cn } from "@/lib/cn";
import {
  CSS_CLASS_PRESETS,
  GROUP_XML_PRESETS,
  PLACEHOLDER_TTYPES,
  WIDGET_OPTION_PRESETS,
  modifierToMode,
  modeToModifier,
  parseGroupsAttr,
  serializeGroupsAttr,
  type FieldModifierMode,
  type GroupVisibilityToken,
  type WidgetOption,
} from "@/lib/widgetCatalog";

type ModifierValue = boolean | string | undefined;

export type InspectorLoadState = "idle" | "loading" | "ready" | "error";

type FieldModifierProps = {
  label: string;
  hint: string;
  value: ModifierValue;
  onChange: (value: ModifierValue) => void;
};

function hasDomainValue(value: ModifierValue): value is string {
  return typeof value === "string" && value.trim() !== "" && value.trim() !== "[]";
}

function FieldModifierEditor({ label, hint, value, onChange }: FieldModifierProps) {
  // Empty "When…" must stay selected while the operator builds a domain.
  // modeToModifier("domain", "[]") is undefined → would snap back to Off without this.
  const [whenOpen, setWhenOpen] = useState(false);
  const derived = modifierToMode(value);
  const mode: FieldModifierMode =
    whenOpen || derived === "domain" ? "domain" : derived;
  const domain = hasDomainValue(value) ? value : "[]";

  useEffect(() => {
    if (hasDomainValue(value)) setWhenOpen(false);
  }, [value]);

  function setMode(next: FieldModifierMode) {
    if (next === "domain") {
      setWhenOpen(true);
      if (!hasDomainValue(value)) {
        onChange(undefined);
      }
      return;
    }
    setWhenOpen(false);
    onChange(modeToModifier(next, "[]"));
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-ink">{label}</span>
        <Tooltip label={hint}>
          <button
            type="button"
            className="text-muted hover:text-ink"
            aria-label={`${label} help`}
          >
            <HelpCircle className="h-3.5 w-3.5" />
          </button>
        </Tooltip>
      </div>
      <div
        className="inline-flex w-full rounded-md border border-border-subtle bg-surface-muted p-0.5"
        role="group"
        aria-label={label}
      >
        {(["off", "always", "domain"] as const).map((m) => (
          <button
            key={m}
            type="button"
            data-testid={`inspector-modifier-${label.toLowerCase()}-${m}`}
            className={cn(
              "flex-1 rounded-[5px] px-2 py-1 text-[11px] font-medium transition-colors",
              mode === m
                ? "bg-surface-raised text-ink shadow-subtle"
                : "text-muted hover:text-ink",
            )}
            onClick={() => setMode(m)}
          >
            {m === "off" ? "Off" : m === "always" ? "Always" : "When…"}
          </button>
        ))}
      </div>
      {mode === "domain" ? (
        <div className="rounded-md border border-border-subtle bg-surface px-2 py-2">
          <DomainBuilder
            value={domain}
            onChange={(d) => {
              const trimmed = d.trim();
              if (!trimmed || trimmed === "[]") {
                setWhenOpen(true);
                onChange(undefined);
                return;
              }
              setWhenOpen(false);
              onChange(trimmed);
            }}
          />
        </div>
      ) : null}
    </div>
  );
}

function GroupVisibilityEditor({
  value,
  onChange,
  groups,
  groupsState,
}: {
  value: string | undefined;
  onChange: (next: string | undefined) => void;
  groups: GroupRow[];
  groupsState: InspectorLoadState;
}) {
  const tokens = parseGroupsAttr(value);
  const [xmlDraft, setXmlDraft] = useState("");

  function commit(next: GroupVisibilityToken[]) {
    onChange(serializeGroupsAttr(next));
  }

  function addToken(xmlId: string, forbid: boolean) {
    const id = xmlId.trim();
    if (!id) return;
    if (tokens.some((t) => t.xmlId === id && t.forbid === forbid)) return;
    commit([...tokens.filter((t) => t.xmlId !== id), { xmlId: id, forbid }]);
    setXmlDraft("");
  }

  const presetOptions = GROUP_XML_PRESETS.filter(
    (p) => !tokens.some((t) => t.xmlId === p.xmlId),
  ).map((p) => ({ value: p.xmlId, label: p.label }));

  return (
    <div className="space-y-3" data-testid="inspector-groups">
      <p className="text-[11px] leading-snug text-muted">
        Odoo <code className="text-ink">groups=</code> uses xml ids. Visible-to
        lists who can see the field; hide-from prefixes the id with{" "}
        <code className="text-ink">!</code>.
      </p>
      {tokens.length ? (
        <ul className="flex flex-wrap gap-1.5">
          {tokens.map((tok) => (
            <li key={`${tok.forbid ? "!" : ""}${tok.xmlId}`}>
              <span
                className={cn(
                  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px]",
                  tok.forbid
                    ? "border-danger/20 bg-danger-subtle text-danger-strong"
                    : "border-border-subtle bg-surface-muted text-ink",
                )}
              >
                {tok.forbid ? "Hide · " : ""}
                {GROUP_XML_PRESETS.find((p) => p.xmlId === tok.xmlId)?.label ?? tok.xmlId}
                <button
                  type="button"
                  className="text-muted hover:text-ink"
                  aria-label={`Remove ${tok.xmlId}`}
                  onClick={() =>
                    commit(tokens.filter((t) => !(t.xmlId === tok.xmlId && t.forbid === tok.forbid)))
                  }
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-[11px] text-muted">Visible to everyone who can open the view.</p>
      )}
      {presetOptions.length ? (
        <Select
          label="Add a common group"
          options={[{ value: "", label: "Choose a group" }, ...presetOptions]}
          value=""
          onChange={(e) => {
            if (e.target.value) addToken(e.target.value, false);
          }}
        />
      ) : null}
      <div className="flex items-end gap-2">
        <div className="min-w-0 flex-1">
          <Input
            label="Xml id"
            data-testid="inspector-groups-xml"
            value={xmlDraft}
            onChange={(e) => setXmlDraft(e.target.value)}
            placeholder="base.group_user"
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addToken(xmlDraft, false);
              }
            }}
          />
        </div>
        <Button
          type="button"
          size="sm"
          onClick={() => addToken(xmlDraft, false)}
          disabled={!xmlDraft.trim()}
        >
          Allow
        </Button>
        <Button
          type="button"
          size="sm"
          onClick={() => addToken(xmlDraft, true)}
          disabled={!xmlDraft.trim()}
        >
          Hide
        </Button>
      </div>
      {groupsState === "loading" ? (
        <p className="text-[11px] text-muted">Loading groups on this database…</p>
      ) : null}
      {groupsState === "error" ? (
        <p className="text-[11px] text-muted">
          Could not load groups. Paste an xml id above — the view still saves{" "}
          <code className="text-ink">groups=</code>.
        </p>
      ) : null}
      {groupsState === "ready" && groups.length === 0 ? (
        <p className="text-[11px] text-muted">No groups returned for this connection.</p>
      ) : null}
      {groupsState === "ready" && groups.length > 0 ? (
        <Disclosure title="Browse groups on this database" testId="inspector-groups-browse">
          <ul className="max-h-36 space-y-1 overflow-auto text-xs">
            {groups.slice(0, 80).map((g) => (
              <li key={g.id} className="flex items-center justify-between gap-2 text-muted">
                <span className="truncate">{g.full_name || g.name}</span>
                <span className="shrink-0 font-mono text-[10px] text-subtle">#{g.id}</span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[11px] text-muted">
            Names here are for reference. Arch needs the xml id (module.name), not the numeric id.
          </p>
        </Disclosure>
      ) : null}
    </div>
  );
}

function RelatedFieldPicker({
  currentName,
  relatedPath,
  relatedPaths,
  relatedState,
  fieldsOnModel,
  viewFieldNames,
  onAddToView,
}: {
  currentName: string;
  relatedPath?: string | null;
  relatedPaths: RelatedPathOption[];
  relatedState: InspectorLoadState;
  fieldsOnModel: FieldRow[];
  viewFieldNames: string[];
  onAddToView?: (fieldName: string) => void;
}) {
  const [picked, setPicked] = useState(relatedPath ?? "");

  useEffect(() => {
    setPicked(relatedPath ?? "");
  }, [relatedPath, currentName]);

  const options = relatedPaths.map((p) => ({
    value: p.path,
    label: `${p.label} · ${p.path}`,
    keywords: [p.path, p.ttype],
  }));

  const match = fieldsOnModel.find(
    (f) => f.related === (picked || relatedPath) && (picked || relatedPath),
  );
  const path = picked || relatedPath || "";
  const alreadyOnView = match ? viewFieldNames.includes(match.name) : false;
  const isThisField = match?.name === currentName;

  return (
    <div className="space-y-2" data-testid="inspector-related">
      {relatedPath ? (
        <p className="text-[11px] leading-snug text-muted">
          This field reads{" "}
          <code className="font-mono text-ink">{relatedPath}</code> on the model.
          Changing the ORM path lives in Models &amp; Fields.
        </p>
      ) : (
        <p className="text-[11px] leading-snug text-muted">
          Pick a relation path (for example Customer → Email) from public field
          metadata. Dotted names are not valid view field names until a related
          column exists on the model.
        </p>
      )}
      {relatedState === "loading" ? (
        <p className="text-[11px] text-muted">Loading relation paths…</p>
      ) : null}
      {relatedState === "error" ? (
        <p className="text-[11px] text-muted">
          Could not load relation paths. Check the connection and retry.
        </p>
      ) : null}
      {relatedState === "ready" && relatedPaths.length === 0 ? (
        <p className="text-[11px] text-muted">
          No many2one paths on this model yet.
        </p>
      ) : null}
      {relatedState === "ready" && relatedPaths.length > 0 ? (
        <Combobox
          options={options}
          value={path}
          onValueChange={setPicked}
          placeholder="Search Customer → Email"
          emptyLabel="No matching path"
        />
      ) : null}
      {path ? (
        <p className="font-mono text-[11px] text-muted" data-testid="inspector-related-path">
          {path}
        </p>
      ) : null}
      {match && isThisField ? (
        <Badge variant="info">This field</Badge>
      ) : null}
      {match && !isThisField ? (
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="default">{match.name}</Badge>
          {alreadyOnView ? (
            <span className="text-[11px] text-muted">Already on this view</span>
          ) : onAddToView ? (
            <Button
              type="button"
              size="sm"
              data-testid="inspector-related-add"
              onClick={() => onAddToView(match.name)}
            >
              Add to view
            </Button>
          ) : null}
        </div>
      ) : null}
      {path && !match ? (
        <p className="text-[11px] text-muted">
          No field on this model uses that path yet. Create it in Models &amp; Fields,
          then place it here.
        </p>
      ) : null}
    </div>
  );
}

function WidgetOptionsEditor({
  widget,
  options,
  onChange,
}: {
  widget: string | undefined;
  options: string | undefined;
  onChange: (options: string | undefined) => void;
}) {
  const presets = widget ? WIDGET_OPTION_PRESETS[widget] ?? [] : [];
  const known = presets.some((p) => p.options === (options ?? ""));

  return (
    <div className="space-y-2">
      {presets.length ? (
        <Select
          label="Options"
          data-testid="inspector-widget-options"
          value={known ? (options ?? "") : "__custom__"}
          onChange={(e) => {
            if (e.target.value === "__custom__") return;
            onChange(e.target.value || undefined);
          }}
          options={[
            { value: "", label: "Default" },
            ...presets.map((p) => ({ value: p.options, label: p.label })),
            ...(!known && options ? [{ value: "__custom__", label: "Custom JSON" }] : []),
          ]}
        />
      ) : null}
      <Disclosure
        title={presets.length ? "Edit options JSON" : "Widget options"}
        defaultOpen={!presets.length && Boolean(options)}
        testId="inspector-options-json"
      >
        <Textarea
          data-testid="inspector-options"
          value={options ?? ""}
          onChange={(e) => onChange(e.target.value.trim() ? e.target.value : undefined)}
          placeholder='{"key": true}'
          rows={3}
          className="font-mono text-xs"
          hint="Written as the field options= attribute."
        />
      </Disclosure>
    </div>
  );
}

export type DesignerFieldInspectorValues = {
  name?: string;
  string?: string;
  required?: ModifierValue;
  readonly?: ModifierValue;
  invisible?: ModifierValue;
  widget?: string;
  options?: string;
  ttype?: string;
  help?: string;
  placeholder?: string;
  class_name?: string;
  groups?: string;
};

export type DesignerFieldInspectorProps = {
  field: DesignerFieldInspectorValues;
  fieldMeta?: FieldRow | null;
  widgetOptions: WidgetOption[];
  widgetAdvanced: boolean;
  onWidgetAdvancedChange: (v: boolean) => void;
  onChange: (patch: Partial<DesignerFieldInspectorValues>) => void;
  groups?: GroupRow[];
  groupsState?: InspectorLoadState;
  relatedPaths?: RelatedPathOption[];
  relatedState?: InspectorLoadState;
  fieldsOnModel?: FieldRow[];
  viewFieldNames?: string[];
  onAddRelatedField?: (fieldName: string) => void;
  onRemoveFromView?: () => void;
};

export function DesignerFieldInspector({
  field,
  fieldMeta,
  widgetOptions,
  widgetAdvanced,
  onWidgetAdvancedChange,
  onChange,
  groups = [],
  groupsState = "idle",
  relatedPaths = [],
  relatedState = "idle",
  fieldsOnModel = [],
  viewFieldNames = [],
  onAddRelatedField,
  onRemoveFromView,
}: DesignerFieldInspectorProps) {
  const ttype = fieldMeta?.ttype ?? field.ttype ?? "";
  const showPlaceholder = !ttype || PLACEHOLDER_TTYPES.has(ttype);
  const classOptions = CSS_CLASS_PRESETS.map((p) => ({ value: p.value, label: p.label }));
  if (field.class_name && !classOptions.some((o) => o.value === field.class_name)) {
    classOptions.push({ value: field.class_name, label: field.class_name });
  }
  const widgetInCatalog = widgetOptions.some((w) => w.id === (field.widget ?? ""));
  const widgetSelectValue =
    !field.widget || widgetInCatalog || widgetAdvanced ? (field.widget ?? "") : field.widget;

  return (
    <div
      className="w-inspector max-w-full space-y-2 text-ui-body text-ink"
      data-testid="designer-field-inspector"
    >
      <header className="space-y-1 px-0.5 pb-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <p className="text-ui-mono text-muted" data-testid="inspector-field-name">
            {field.name ?? fieldMeta?.name ?? "field"}
          </p>
          {ttype ? <Badge variant="default">{ttype}</Badge> : null}
          {fieldMeta?.related ? <Badge variant="info">Related</Badge> : null}
          {fieldMeta?.required ? <Badge variant="warning">ORM required</Badge> : null}
        </div>
        <p className="text-ui-title text-ink">
          {field.string || fieldMeta?.field_description || "Untitled field"}
        </p>
      </header>

      <Disclosure
        title="Selection"
        defaultOpen
        sticky
        testId="inspector-section-selection"
      >
        <Input
          label="Label"
          data-testid="inspector-label"
          value={field.string ?? ""}
          onChange={(e) =>
            onChange({ string: e.target.value.trim() ? e.target.value : undefined })
          }
          placeholder={fieldMeta?.field_description || "Display label"}
          hint="Writes string= on this view. Does not rename the column."
        />
        <RelatedFieldPicker
          currentName={field.name ?? ""}
          relatedPath={fieldMeta?.related}
          relatedPaths={relatedPaths}
          relatedState={relatedState}
          fieldsOnModel={fieldsOnModel}
          viewFieldNames={viewFieldNames}
          onAddToView={onAddRelatedField}
        />
      </Disclosure>

      <Disclosure title="Layout" sticky testId="inspector-section-layout">
        <Textarea
          label="Help tooltip"
          data-testid="inspector-help"
          value={field.help ?? ""}
          onChange={(e) =>
            onChange({ help: e.target.value.trim() ? e.target.value : undefined })
          }
          placeholder={fieldMeta?.help || "Shown when the user hovers the label"}
          rows={2}
          hint={
            fieldMeta?.help && !field.help
              ? "Field definition already has help — fill this to override it on the view."
              : "Persists as help= on the field in arch."
          }
        />
        {showPlaceholder ? (
          <Input
            label="Placeholder"
            data-testid="inspector-placeholder"
            value={field.placeholder ?? ""}
            onChange={(e) =>
              onChange({
                placeholder: e.target.value.trim() ? e.target.value : undefined,
              })
            }
            placeholder="Empty-state hint"
            hint="Odoo placeholder= on char, text, and similar widgets."
          />
        ) : null}
        <Select
          label="CSS class"
          data-testid="inspector-class"
          value={field.class_name ?? ""}
          onChange={(e) => onChange({ class_name: e.target.value || undefined })}
          options={[{ value: "", label: "None" }, ...classOptions]}
          hint="Written as class= on the field tag (Odoo uses class, not className)."
        />
      </Disclosure>

      <Disclosure title="Attributes" sticky testId="inspector-section-attributes">
        <FieldModifierEditor
          label="Required"
          hint="View-layer required. ORM required on the field definition still applies."
          value={field.required}
          onChange={(required) => onChange({ required })}
        />
        <FieldModifierEditor
          label="Readonly"
          hint="View-layer readonly. Related fields are typically readonly on the model too."
          value={field.readonly}
          onChange={(readonly) => onChange({ readonly })}
        />
        <FieldModifierEditor
          label="Invisible"
          hint="Hide the field entirely, always, or when a domain matches."
          value={field.invisible}
          onChange={(invisible) => onChange({ invisible })}
        />
        <Disclosure
          title="Group visibility"
          defaultOpen={Boolean(field.groups)}
          testId="inspector-groups-disclosure"
        >
          <GroupVisibilityEditor
            value={field.groups}
            onChange={(groupsValue) => onChange({ groups: groupsValue })}
            groups={groups}
            groupsState={groupsState}
          />
        </Disclosure>
        {widgetAdvanced ? (
          <Input
            label="Widget"
            data-testid="inspector-widget-advanced"
            value={field.widget ?? ""}
            onChange={(e) => onChange({ widget: e.target.value || undefined })}
            placeholder="Advanced widget name"
            className="font-mono"
            hint="Escape hatch for widgets not in the curated list."
          />
        ) : (
          <Select
            label="Widget"
            data-testid="inspector-widget"
            value={widgetSelectValue}
            onChange={(e) => onChange({ widget: e.target.value || undefined })}
            options={[
              { value: "", label: "Default" },
              ...widgetOptions.map((w) => ({ value: w.id, label: w.label })),
              ...(!widgetInCatalog && field.widget
                ? [{ value: field.widget, label: `${field.widget} (current)` }]
                : []),
            ]}
          />
        )}
        <button
          type="button"
          className="text-ui-label text-accent hover:underline"
          onClick={() => onWidgetAdvancedChange(!widgetAdvanced)}
        >
          {widgetAdvanced ? "Use curated list" : "Enter widget name"}
        </button>
        <WidgetOptionsEditor
          widget={field.widget}
          options={field.options}
          onChange={(options) => onChange({ options })}
        />
      </Disclosure>

      <Disclosure title="Inherit" sticky testId="inspector-section-inherit">
        <p className="text-ui-meta text-muted">
          View-layer only. Advanced XPath inherit lives on the Tools rail — progressive
          disclosure, not a second canvas.
        </p>
        <div
          className="rounded-md border border-border-subtle bg-surface-muted/60 px-3 py-3"
          data-testid="inspector-remove-copy"
        >
          <p className="text-ui-label text-ink">Remove from view</p>
          <p className="mt-1 text-ui-meta leading-snug text-muted">
            Removing a field from this view does not delete the database column. Type,
            selection keys, and relation stay under Models &amp; Fields.
          </p>
          {onRemoveFromView ? (
            <Button
              type="button"
              size="sm"
              className="mt-3"
              data-testid="inspector-remove"
              onClick={onRemoveFromView}
            >
              Remove from view
            </Button>
          ) : null}
        </div>
      </Disclosure>
    </div>
  );
}

export function DesignerFieldInspectorEmpty() {
  return (
    <div className="py-6 text-center" data-testid="designer-field-inspector-empty">
      <p className="text-sm font-medium text-ink">No field selected</p>
      <p className="mt-1 text-xs leading-relaxed text-muted">
        Select a field on the canvas to edit label, help, modifiers, widget, and
        related path. Removing it from the view does not delete the column.
      </p>
    </div>
  );
}
