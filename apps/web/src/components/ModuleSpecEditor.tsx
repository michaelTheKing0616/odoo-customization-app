"use client";

import { useMemo, useState } from "react";
import { cn } from "@/lib/cn";
import { defaultModel, moduleSpecSummary } from "@/lib/modulespec-journey";
import {
  MODULESPEC_SECTIONS,
  customCodeBlocks,
  ensureAccessRules,
  ensureMenus,
  ensureModels,
  ensureViews,
  type ModuleSpecDoc,
  type ModuleSpecField,
  type ModuleSpecModel,
  type ModuleSpecSection,
} from "@/lib/modulespec-types";
import { ModuleSpecCustomCodePanel } from "@/components/modulespec/ModuleSpecCustomCodePanel";
import { ModuleSpecExtrasPanel } from "@/components/modulespec/ModuleSpecExtrasPanel";
import { ModuleSpecFieldsTable } from "@/components/modulespec/ModuleSpecFieldsTable";
import { ModuleSpecJsonDisclosure } from "@/components/modulespec/ModuleSpecJsonDisclosure";
import { ModuleSpecMenusPanel } from "@/components/modulespec/ModuleSpecMenusPanel";
import { ModuleSpecModelsPanel } from "@/components/modulespec/ModuleSpecModelsPanel";
import { ModuleSpecRelationsPanel } from "@/components/modulespec/ModuleSpecRelationsPanel";
import { ModuleSpecSecurityPanel } from "@/components/modulespec/ModuleSpecSecurityPanel";
import { ModuleSpecViewsPanel } from "@/components/modulespec/ModuleSpecViewsPanel";

export type {
  ModuleSpecDoc,
  ModuleSpecField,
  ModuleSpecModel,
} from "@/lib/modulespec-types";

type Props = {
  value: ModuleSpecDoc;
  onChange: (next: ModuleSpecDoc) => void;
  readOnly?: boolean;
  canEditCustomCode?: boolean;
  onLintBlocks?: () => void;
  onExportSandbox?: () => void;
  lintBusy?: boolean;
  sandboxBusy?: boolean;
  designerHref?: string;
};

export function ModuleSpecEditor({
  value,
  onChange,
  readOnly,
  canEditCustomCode = false,
  onLintBlocks,
  onExportSandbox,
  lintBusy,
  sandboxBusy,
  designerHref,
}: Props) {
  const [section, setSection] = useState<ModuleSpecSection>("models");
  const [selectedModel, setSelectedModel] = useState(0);
  const models = ensureModels(value);
  const model = models[selectedModel];
  const blocks = useMemo(() => customCodeBlocks(value), [value]);
  const summary = moduleSpecSummary(value);

  function patch(partial: Partial<ModuleSpecDoc>) {
    onChange({ ...value, ...partial });
  }

  function updateModels(next: ModuleSpecModel[]) {
    patch({ models: next });
  }

  function updateModel(index: number, next: ModuleSpecModel) {
    const copy = ensureModels(value);
    copy[index] = next;
    updateModels(copy);
  }

  function addModel() {
    updateModels([...models, defaultModel(models.length)]);
    setSelectedModel(models.length);
    setSection("models");
  }

  function removeModel(index: number) {
    const copy = models.filter((_, i) => i !== index);
    updateModels(copy);
    setSelectedModel(Math.max(0, Math.min(selectedModel, copy.length - 1)));
  }

  function addField() {
    if (!model) return;
    const fields = [...(model.fields || [])];
    fields.push({ name: `x_field_${fields.length + 1}`, ttype: "char", string: "Field" });
    updateModel(selectedModel, { ...model, fields });
  }

  function updateField(index: number, field: ModuleSpecField) {
    if (!model) return;
    const fields = [...(model.fields || [])];
    fields[index] = field;
    updateModel(selectedModel, { ...model, fields });
  }

  function removeField(index: number) {
    if (!model) return;
    updateModel(selectedModel, {
      ...model,
      fields: (model.fields || []).filter((_, i) => i !== index),
    });
  }

  function updateCustomBlocks(next: Array<Record<string, unknown>>) {
    patch({ custom_code_blocks: next, unmapped: undefined });
  }

  const counts: Record<ModuleSpecSection, number> = {
    models: summary.models,
    views: summary.views,
    menus: summary.menus,
    security: summary.access,
    relations: 0,
    extras: summary.smart + summary.autos,
    custom_code: summary.customCode,
  };

  return (
    <div className="border border-border-subtle bg-surface-muted/40" data-testid="modulespec-editor">
      <div className="ms-section-nav" role="tablist" aria-label="ModuleSpec sections">
        {MODULESPEC_SECTIONS.map((row) => (
          <button
            key={row.id}
            type="button"
            role="tab"
            aria-selected={section === row.id}
            onClick={() => setSection(row.id)}
            className={cn("ms-section-tab", section === row.id && "is-current")}
            data-section={row.id}
          >
            {row.label}
            {row.id !== "relations" ? (
              <span className="ms-section-count">{counts[row.id]}</span>
            ) : null}
          </button>
        ))}
      </div>

      <div className="p-4">
        {section === "models" ? (
          <ModuleSpecModelsPanel
            models={models}
            selectedIndex={selectedModel}
            readOnly={readOnly}
            onSelect={setSelectedModel}
            onAdd={addModel}
            onRemove={removeModel}
            onPatch={updateModel}
          >
            <ModuleSpecFieldsTable
              fields={model?.fields || []}
              readOnly={readOnly}
              onAdd={addField}
              onUpdate={updateField}
              onRemove={removeField}
            />
          </ModuleSpecModelsPanel>
        ) : null}

        {section === "views" ? (
          <ModuleSpecViewsPanel
            views={ensureViews(value)}
            readOnly={readOnly}
            designerHref={designerHref}
            onChange={(views) => patch({ views })}
          />
        ) : null}

        {section === "menus" ? (
          <ModuleSpecMenusPanel
            menus={ensureMenus(value)}
            readOnly={readOnly}
            onChange={(menus) => patch({ menus })}
          />
        ) : null}

        {section === "security" ? (
          <ModuleSpecSecurityPanel
            rules={ensureAccessRules(value)}
            readOnly={readOnly}
            onChange={(access_rules) => patch({ access_rules })}
          />
        ) : null}

        {section === "relations" ? (
          <ModuleSpecRelationsPanel
            spec={value}
            onSelectModel={(modelName) => {
              const index = models.findIndex((row) => row.model === modelName);
              if (index >= 0) {
                setSelectedModel(index);
                setSection("models");
              }
            }}
          />
        ) : null}

        {section === "extras" ? (
          <ModuleSpecExtrasPanel
            smartButtons={Array.isArray(value.smart_buttons) ? value.smart_buttons : []}
            automations={Array.isArray(value.automations) ? value.automations : []}
          />
        ) : null}

        {section === "custom_code" ? (
          <ModuleSpecCustomCodePanel
            blocks={blocks}
            readOnly={readOnly}
            canEditCustomCode={canEditCustomCode}
            lintBusy={lintBusy}
            sandboxBusy={sandboxBusy}
            onAdd={() =>
              updateCustomBlocks([
                ...blocks,
                {
                  source_file: "models/custom_logic.py",
                  kind: "python",
                  content: "from odoo import api, fields, models\n\n# Custom logic\n",
                  reason: "authoring",
                },
              ])
            }
            onUpdate={(index, partial) =>
              updateCustomBlocks(blocks.map((row, i) => (i === index ? { ...row, ...partial } : row)))
            }
            onRemove={(index) => updateCustomBlocks(blocks.filter((_, i) => i !== index))}
            onLintBlocks={onLintBlocks}
            onExportSandbox={onExportSandbox}
          />
        ) : null}
      </div>

      <div className="border-t border-border-subtle px-4 py-3">
        <ModuleSpecJsonDisclosure value={value} readOnly={readOnly} onChange={onChange} />
      </div>
    </div>
  );
}
