"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/layout-primitives";
import { IconViews } from "@/components/ui/icons";
import type { ModuleSpecView } from "@/lib/modulespec-types";

type ModuleSpecViewsPanelProps = {
  views: ModuleSpecView[];
  readOnly?: boolean;
  designerHref?: string;
  onChange: (next: ModuleSpecView[]) => void;
};

const VIEW_TYPES = ["form", "list", "search", "kanban", "activity"];

export function ModuleSpecViewsPanel({
  views,
  readOnly,
  designerHref,
  onChange,
}: ModuleSpecViewsPanelProps) {
  const [openIndex, setOpenIndex] = useState<number | null>(views.length ? 0 : null);

  function patch(index: number, partial: Partial<ModuleSpecView>) {
    onChange(views.map((row, i) => (i === index ? { ...row, ...partial } : row)));
  }

  function addView() {
    const next: ModuleSpecView = {
      name: "x_new.form",
      model: "x_new_model_1",
      type: "form",
      mode: "primary",
      arch: "<form><sheet><group><field name=\"x_name\"/></group></sheet></form>",
    };
    onChange([...views, next]);
    setOpenIndex(views.length);
  }

  return (
    <div className="space-y-3" data-testid="modulespec-views">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">Views</h3>
        <div className="flex gap-2">
          {designerHref ? (
            <Button asChild variant="ghost" size="sm">
              <a href={designerHref}>Open View Designer</a>
            </Button>
          ) : null}
          {!readOnly ? (
            <Button type="button" variant="secondary" size="sm" onClick={addView}>
              Add view
            </Button>
          ) : null}
        </div>
      </div>
      {views.length === 0 ? (
        <EmptyState
          icon={<IconViews className="h-5 w-5" />}
          title="No views in this spec"
          description="Generate UI can emit default list and form views. Add an arch here when you need to review or pin inherit XML."
        />
      ) : (
        <ul className="space-y-2">
          {views.map((view, index) => {
            const open = openIndex === index;
            return (
              <li key={`${view.name}-${index}`} className="rounded-md border border-border-subtle bg-surface-raised p-3">
                <button
                  type="button"
                  className="flex w-full flex-wrap items-center gap-2 text-left"
                  onClick={() => setOpenIndex(open ? null : index)}
                >
                  <span className="font-mono text-xs text-ink">{view.name || "unnamed view"}</span>
                  <Badge variant="default">{view.type || "form"}</Badge>
                  <span className="text-xs text-muted">{view.model}</span>
                  <span className="ml-auto text-xs text-muted">{view.mode || "primary"}</span>
                </button>
                {open ? (
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <label className="text-sm">
                      <span className="studio-field-label">Name</span>
                      <input
                        disabled={readOnly}
                        value={view.name ?? ""}
                        onChange={(event) => patch(index, { name: event.target.value })}
                        className="input mt-1 font-mono text-xs"
                      />
                    </label>
                    <label className="text-sm">
                      <span className="studio-field-label">Model</span>
                      <input
                        disabled={readOnly}
                        value={view.model ?? ""}
                        onChange={(event) => patch(index, { model: event.target.value })}
                        className="input mt-1 font-mono text-xs"
                      />
                    </label>
                    <label className="text-sm">
                      <span className="studio-field-label">Type</span>
                      <select
                        disabled={readOnly}
                        value={view.type || "form"}
                        onChange={(event) => patch(index, { type: event.target.value })}
                        className="input mt-1"
                      >
                        {VIEW_TYPES.map((type) => (
                          <option key={type} value={type}>
                            {type}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="text-sm">
                      <span className="studio-field-label">Mode</span>
                      <input
                        disabled={readOnly}
                        value={view.mode ?? ""}
                        onChange={(event) => patch(index, { mode: event.target.value })}
                        className="input mt-1"
                      />
                    </label>
                    <label className="text-sm md:col-span-2">
                      <span className="studio-field-label">Arch</span>
                      <textarea
                        disabled={readOnly}
                        value={view.arch ?? ""}
                        onChange={(event) => patch(index, { arch: event.target.value })}
                        rows={8}
                        className="textarea mt-1 font-mono text-xs"
                      />
                    </label>
                    {!readOnly ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => onChange(views.filter((_, i) => i !== index))}
                      >
                        Remove view
                      </Button>
                    ) : null}
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
