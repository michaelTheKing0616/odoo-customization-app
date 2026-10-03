"use client";

import { OverviewViewsPanel } from "@/components/overview/OverviewViewsPanel";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/DataTable";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/layout-primitives";
import { OVERVIEW_BROWSER_TABS } from "./overview-columns";
import type { OverviewPageModel } from "./use-overview-page";

export function OverviewModelsSection({ vm }: { vm: OverviewPageModel }) {
  return (
    <>
      <div className="flex flex-wrap gap-2 border-b border-border-subtle pb-3">
        {OVERVIEW_BROWSER_TABS.map((t) => (
          <Button
            key={t.id}
            type="button"
            variant={vm.tab === t.id ? "primary" : "secondary"}
            size="sm"
            onClick={() => vm.setTab(t.id)}
          >
            {t.label}
          </Button>
        ))}
      </div>
      {(vm.tab === "fields" || vm.tab === "views") && (
        <div className="mt-4 max-w-xl space-y-2">
          <p className="text-xs text-muted" data-testid="model-picker-count">
            {vm.models.length} models on this connection
          </p>
          {vm.models.length > 40 ? (
            <Input
              placeholder="Filter models…"
              value={vm.modelPickerQuery}
              onChange={(e) => vm.setModelPickerQuery(e.target.value)}
              aria-label="Filter model list"
            />
          ) : null}
          <Select
            label="Model"
            value={vm.selectedModel}
            onChange={(e) => vm.setSelectedModel(e.target.value)}
            options={(() => {
              const q = vm.modelPickerQuery.trim().toLowerCase();
              let list = q
                ? vm.models.filter(
                    (m) =>
                      m.model.toLowerCase().includes(q) ||
                      (m.name ?? "").toLowerCase().includes(q),
                  )
                : vm.models;
              if (
                vm.selectedModel &&
                !list.some((m) => m.model === vm.selectedModel)
              ) {
                const selected = vm.models.find((m) => m.model === vm.selectedModel);
                if (selected) list = [selected, ...list];
              }
              return list.map((m) => ({
                value: m.model,
                label: `${m.name || m.model} (${m.model})`,
              }));
            })()}
          />
        </div>
      )}
      {vm.loading ? (
        <div className="mt-4 space-y-2">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
      ) : null}
      {!vm.loading && vm.tab === "modules" ? (
        <div className="mt-6">
          <DataTable columns={vm.moduleColumns} rows={vm.modules} rowKey={(m) => String(m.id)} />
        </div>
      ) : null}
      {!vm.loading && vm.tab === "models" ? (
        <div className="mt-6 space-y-4">
          <Input
            placeholder="Filter models…"
            value={vm.modelQuery}
            onChange={(e) => vm.setModelQuery(e.target.value)}
            className="max-w-md"
          />
          <DataTable columns={vm.modelColumns} rows={vm.filteredModels} rowKey={(m) => String(m.id)} />
        </div>
      ) : null}
      {!vm.loading && vm.tab === "fields" ? (
        <div className="mt-6">
          <DataTable columns={vm.fieldColumns} rows={vm.fields} rowKey={(f) => String(f.id)} />
        </div>
      ) : null}
      {!vm.loading && vm.tab === "views" ? (
        <OverviewViewsPanel model={vm.selectedModel} views={vm.views} />
      ) : null}
    </>
  );
}
