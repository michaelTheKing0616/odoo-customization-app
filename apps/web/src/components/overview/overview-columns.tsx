import { ModelTierInline } from "@/components/ModelTierInline";
import type { DataTableColumn } from "@/components/ui/DataTable";
import type { FieldRow, ModelRow, ModuleRow } from "@/lib/api";
import type { OverviewBrowserTab } from "./use-overview-page-state";

export const OVERVIEW_BROWSER_TABS: { id: OverviewBrowserTab; label: string }[] = [
  { id: "modules", label: "Apps" },
  { id: "models", label: "Models" },
  { id: "fields", label: "Fields" },
  { id: "views", label: "Views" },
];

export function overviewModuleColumns(): DataTableColumn<ModuleRow>[] {
  return [
    {
      id: "label",
      header: "Name",
      accessor: (m) => m.shortdesc ?? m.name,
      sortValue: (m) => m.shortdesc ?? m.name,
    },
    {
      id: "name",
      header: "Technical",
      accessor: (m) => <span className="font-mono text-accent">{m.name}</span>,
      sortValue: (m) => m.name,
    },
    {
      id: "state",
      header: "State",
      accessor: (m) => m.state ?? "—",
      sortValue: (m) => m.state ?? "",
    },
  ];
}

export function overviewModelColumns(
  connectionId: string,
): DataTableColumn<ModelRow>[] {
  return [
    {
      id: "label",
      header: "Label",
      accessor: (m) => m.name,
      sortValue: (m) => m.name,
    },
    {
      id: "model",
      header: "Model",
      accessor: (m) => <span className="font-mono text-accent">{m.model}</span>,
      sortValue: (m) => m.model,
    },
    {
      id: "tier",
      header: "PCM",
      accessor: (m) => <ModelTierInline connectionId={connectionId} model={m.model} />,
    },
    {
      id: "state",
      header: "State",
      accessor: (m) => m.state ?? "—",
      sortValue: (m) => m.state ?? "",
    },
  ];
}

export function overviewFieldColumns(): DataTableColumn<FieldRow>[] {
  return [
    {
      id: "label",
      header: "Label",
      accessor: (f) => f.field_description,
      sortValue: (f) => f.field_description,
    },
    {
      id: "name",
      header: "Name",
      accessor: (f) => <span className="font-mono text-accent">{f.name}</span>,
      sortValue: (f) => f.name,
    },
    {
      id: "type",
      header: "Type",
      accessor: (f) => (
        <>
          {f.ttype}
          {f.relation ? ` → ${f.relation}` : ""}
        </>
      ),
      sortValue: (f) => f.ttype,
    },
    {
      id: "flags",
      header: "Flags",
      accessor: (f) => (
        <span className="text-muted">
          {[f.required && "required", f.readonly && "readonly", f.state]
            .filter(Boolean)
            .join(", ") || "—"}
        </span>
      ),
    },
  ];
}
