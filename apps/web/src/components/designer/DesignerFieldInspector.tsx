"use client";

import { useEffect, useState } from "react";
import { DomainBuilder } from "@/components/DomainBuilder";
import {
  IMAGE_SIZE_PRESETS,
  modifierToMode,
  modeToModifier,
  type FieldModifierMode,
  type WidgetOption,
} from "@/lib/widgetCatalog";

type ModifierValue = boolean | string | undefined;

const FIELD_CONTROL =
  "mt-1 w-full border border-border-subtle bg-surface px-2 py-1.5 text-xs text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent";

type Props = {
  label: string;
  value: ModifierValue;
  onChange: (value: ModifierValue) => void;
};

function hasDomainValue(value: ModifierValue): value is string {
  return typeof value === "string" && value.trim() !== "" && value.trim() !== "[]";
}

function FieldModifierEditor({ label, value, onChange }: Props) {
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
        // Clear Always/Off so we do not keep emitting required="1" while editing.
        onChange(undefined);
      }
      return;
    }
    setWhenOpen(false);
    onChange(modeToModifier(next, "[]"));
  }

  return (
    <div className="space-y-2">
      <span className="text-muted">{label}</span>
      <div className="flex flex-wrap gap-2 text-xs">
        {(["off", "always", "domain"] as const).map((m) => (
          <button
            key={m}
            type="button"
            data-testid={`inspector-modifier-${label.toLowerCase()}-${m}`}
            className={`rounded border px-2 py-1 ${
              mode === m
                ? "border-accent bg-accent/10 text-ink"
                : "border-border-subtle text-muted hover:text-ink"
            }`}
            onClick={() => setMode(m)}
          >
            {m === "off" ? "Off" : m === "always" ? "Always" : "When…"}
          </button>
        ))}
      </div>
      {mode === "domain" ? (
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
      ) : null}
    </div>
  );
}

export type DesignerFieldInspectorValues = {
  string?: string;
  required?: ModifierValue;
  readonly?: ModifierValue;
  invisible?: string;
  widget?: string;
  options?: string;
  ttype?: string;
};

type InspectorProps = {
  field: DesignerFieldInspectorValues;
  widgetOptions: WidgetOption[];
  widgetAdvanced: boolean;
  onWidgetAdvancedChange: (v: boolean) => void;
  onChange: (patch: Partial<DesignerFieldInspectorValues>) => void;
};

export function DesignerFieldInspector({
  field,
  widgetOptions,
  widgetAdvanced,
  onWidgetAdvancedChange,
  onChange,
}: InspectorProps) {
  return (
    <div
      className="mt-3 space-y-3 text-sm text-ink"
      data-testid="designer-field-inspector"
    >
      <label className="block">
        <span className="text-muted">Label</span>
        <input
          data-testid="inspector-label"
          value={field.string ?? ""}
          onChange={(e) =>
            onChange({ string: e.target.value.trim() ? e.target.value : undefined })
          }
          placeholder="Display label (string=)"
          className={FIELD_CONTROL}
        />
      </label>
      <FieldModifierEditor
        label="Required"
        value={field.required}
        onChange={(required) => onChange({ required })}
      />
      <FieldModifierEditor
        label="Readonly"
        value={field.readonly}
        onChange={(readonly) => onChange({ readonly })}
      />
      <DomainBuilder
        label="Invisible (domain)"
        value={field.invisible || "[]"}
        onChange={(domain) =>
          onChange({
            invisible: domain === "[]" ? undefined : domain,
          })
        }
      />
      <label className="block">
        <span className="text-muted">Widget</span>
        {widgetAdvanced ? (
          <input
            data-testid="inspector-widget-advanced"
            value={field.widget ?? ""}
            onChange={(e) =>
              onChange({ widget: e.target.value || undefined })
            }
            placeholder="Advanced widget name"
            className={`${FIELD_CONTROL} font-mono`}
          />
        ) : (
          <select
            data-testid="inspector-widget"
            value={field.widget ?? ""}
            onChange={(e) =>
              onChange({ widget: e.target.value || undefined })
            }
            className={FIELD_CONTROL}
          >
            <option value="">Default</option>
            {widgetOptions.map((w) => (
              <option key={w.id} value={w.id}>
                {w.label}
              </option>
            ))}
          </select>
        )}
        <button
          type="button"
          className="mt-1 text-xs text-accent hover:underline"
          onClick={() => onWidgetAdvancedChange(!widgetAdvanced)}
        >
          {widgetAdvanced ? "Use curated list" : "Advanced…"}
        </button>
      </label>
      {field.widget === "image" ? (
        <label className="block">
          <span className="text-muted">Image size</span>
          <select
            data-testid="inspector-image-size"
            value={field.options ?? ""}
            onChange={(e) =>
              onChange({ options: e.target.value || undefined })
            }
            className={FIELD_CONTROL}
          >
            <option value="">Default</option>
            {IMAGE_SIZE_PRESETS.map((p) => (
              <option key={p.options} value={p.options}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      <p className="text-[11px] leading-snug text-muted">
        These attrs are view-layer (how the form looks/behaves). Field type,
        selection keys, relation, and ORM required live under{" "}
        <strong className="font-medium text-ink">Models &amp; Fields</strong>.
      </p>
    </div>
  );
}
