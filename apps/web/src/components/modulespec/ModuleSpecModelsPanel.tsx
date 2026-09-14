"use client";

import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/layout-primitives";
import { IconModels } from "@/components/ui/icons";
import { cn } from "@/lib/cn";
import { EMPTY_STATES } from "@/lib/copy-guide";
import type { ModuleSpecModel } from "@/lib/modulespec-types";

type ModuleSpecModelsPanelProps = {
  models: ModuleSpecModel[];
  selectedIndex: number;
  readOnly?: boolean;
  onSelect: (index: number) => void;
  onAdd: () => void;
  onRemove: (index: number) => void;
  onPatch: (index: number, next: ModuleSpecModel) => void;
  children?: React.ReactNode;
};

export function ModuleSpecModelsPanel({
  models,
  selectedIndex,
  readOnly,
  onSelect,
  onAdd,
  onRemove,
  onPatch,
  children,
}: ModuleSpecModelsPanelProps) {
  const model = models[selectedIndex];
  return (
    <div className="ms-workbench" data-testid="modulespec-models">
      <aside className="ms-model-rail">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-ink">Models</h3>
          {!readOnly ? (
            <Button type="button" variant="secondary" size="sm" onClick={onAdd} data-testid="modulespec-add-model">
              Add model
            </Button>
          ) : null}
        </div>
        {models.length === 0 ? (
          <EmptyState
            icon={<IconModels className="h-5 w-5" />}
            title="No models yet"
            description={EMPTY_STATES.moduleSpec}
          />
        ) : (
          <ul className="mt-3 space-y-1">
            {models.map((row, index) => (
              <li key={`${row.model}-${index}`}>
                <button
                  type="button"
                  onClick={() => onSelect(index)}
                  className={cn(
                    "w-full rounded-md px-2 py-1.5 text-left",
                    selectedIndex === index
                      ? "bg-surface-raised text-ink"
                      : "text-muted hover:bg-surface-raised hover:text-ink",
                  )}
                  data-testid={`modulespec-model-${index}`}
                >
                  <span className="block truncate font-mono text-xs">{row.model || "unnamed"}</span>
                  <span className="block truncate text-[11px] text-muted">
                    {row.description || "No label"} · {row.fields?.length ?? 0} fields
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>
      <div className="ms-model-detail">
        {!model ? (
          <p className="text-sm text-muted">Select or add a model to edit fields.</p>
        ) : (
          <>
            <div className="flex flex-wrap items-end gap-3">
              <label className="min-w-[12rem] flex-1 text-sm">
                <span className="studio-field-label">Model</span>
                <input
                  disabled={readOnly}
                  value={model.model}
                  onChange={(event) => onPatch(selectedIndex, { ...model, model: event.target.value })}
                  className="input mt-1 font-mono"
                  data-testid="modulespec-model-name"
                />
              </label>
              <label className="min-w-[12rem] flex-1 text-sm">
                <span className="studio-field-label">Label</span>
                <input
                  disabled={readOnly}
                  value={model.description ?? ""}
                  onChange={(event) =>
                    onPatch(selectedIndex, { ...model, description: event.target.value })
                  }
                  className="input mt-1"
                />
              </label>
              <label className="text-sm">
                <span className="studio-field-label">Mode</span>
                <select
                  disabled={readOnly}
                  value={model.mode || "new"}
                  onChange={(event) => onPatch(selectedIndex, { ...model, mode: event.target.value })}
                  className="input mt-1"
                >
                  <option value="new">New</option>
                  <option value="inherit">Inherit</option>
                </select>
              </label>
              {model.is_workflow ? <Badge variant="info">Workflow</Badge> : null}
              {!readOnly ? (
                <Button
                  type="button"
                  variant="danger"
                  size="sm"
                  onClick={() => onRemove(selectedIndex)}
                  data-testid="modulespec-remove-model"
                >
                  Remove model
                </Button>
              ) : null}
            </div>
            {children}
          </>
        )}
      </div>
    </div>
  );
}
