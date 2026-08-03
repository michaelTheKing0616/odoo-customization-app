"use client";

import { DomainBuilder } from "@/components/DomainBuilder";
import {
  IMAGE_SIZE_PRESETS,
  modifierToMode,
  modeToModifier,
  type FieldModifierMode,
  type WidgetOption,
} from "@/lib/widgetCatalog";

type ModifierValue = boolean | string | undefined;

type Props = {
  label: string;
  value: ModifierValue;
  onChange: (value: ModifierValue) => void;
};

function FieldModifierEditor({ label, value, onChange }: Props) {
  const mode = modifierToMode(value);
  const domain =
    mode === "domain" && typeof value === "string" ? value : "[]";

  function setMode(next: FieldModifierMode) {
    onChange(modeToModifier(next, domain));
  }

  return (
    <div className="space-y-2">
      <span className="text-[#a8909e]">{label}</span>
      <div className="flex flex-wrap gap-2 text-xs">
        {(["off", "always", "domain"] as const).map((m) => (
          <button
            key={m}
            type="button"
            className={`rounded border px-2 py-1 ${
              mode === m
                ? "border-[#c9a9c0] bg-[#1a2e28] text-[#d4c4ce]"
                : "border-[#3d2a38] text-[#8f7a88]"
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
          onChange={(d) => onChange(modeToModifier("domain", d))}
        />
      ) : null}
    </div>
  );
}

export type DesignerFieldInspectorValues = {
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
    <div className="mt-3 space-y-3 text-sm">
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
        <span className="text-[#a8909e]">Widget</span>
        {widgetAdvanced ? (
          <input
            value={field.widget ?? ""}
            onChange={(e) =>
              onChange({ widget: e.target.value || undefined })
            }
            placeholder="Advanced widget name"
            className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 font-mono text-xs"
          />
        ) : (
          <select
            value={field.widget ?? ""}
            onChange={(e) =>
              onChange({ widget: e.target.value || undefined })
            }
            className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 text-xs"
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
          className="mt-1 text-xs text-[#c9a9c0]"
          onClick={() => onWidgetAdvancedChange(!widgetAdvanced)}
        >
          {widgetAdvanced ? "Use curated list" : "Advanced…"}
        </button>
      </label>
      {field.widget === "image" ? (
        <label className="block">
          <span className="text-[#a8909e]">Image size</span>
          <select
            value={field.options ?? ""}
            onChange={(e) =>
              onChange({ options: e.target.value || undefined })
            }
            className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 text-xs"
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
    </div>
  );
}
