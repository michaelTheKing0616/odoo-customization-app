"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import type { FieldRow, GroupRow, RelatedPathOption } from "@/lib/api";
import {
  DesignerFieldInspector,
  DesignerFieldInspectorEmpty,
  type DesignerFieldInspectorValues,
} from "@/components/designer/DesignerFieldInspector";
import type {
  DesignerField,
  FormChild,
  ViewType,
} from "@/components/designer/designer-model";
import { fallbackWidgetsForTtype, type WidgetOption } from "@/lib/widgetCatalog";

export type DesignerFieldInspectorDeps = {
  connectionId: string;
  model: string;
  api: {
    listGroups: (connectionId: string) => Promise<GroupRow[]>;
    listRelatedPaths: (
      connectionId: string,
      model: string,
      depth: number,
    ) => Promise<RelatedPathOption[]>;
    listBuilderWidgets: (
      connectionId: string,
      ttype: string,
    ) => Promise<WidgetOption[]>;
  };
  fields: FieldRow[];
  viewType: ViewType;
  formChildren: FormChild[];
  listColumns: DesignerField[];
  searchFields: DesignerField[];
  kanbanFields: DesignerField[];
  selectedField: DesignerField | null;
  updateSelectedField: (patch: Partial<DesignerFieldInspectorValues>) => void;
  removeSelectedField: () => void;
  appendFieldToCurrentLayout: (name: string, rows: FieldRow[]) => void;
};

export function useDesignerFieldInspector(
  deps: DesignerFieldInspectorDeps,
): { fieldInspector: ReactNode } {
  const {
    connectionId,
    model,
    api,
    fields,
    viewType,
    formChildren,
    listColumns,
    searchFields,
    kanbanFields,
    selectedField,
    updateSelectedField,
    removeSelectedField,
    appendFieldToCurrentLayout,
  } = deps;

  const [widgetAdvanced, setWidgetAdvanced] = useState(false);
  const [inspectorWidgets, setInspectorWidgets] = useState<WidgetOption[]>([]);
  const [inspectorGroups, setInspectorGroups] = useState<GroupRow[]>([]);
  const [inspectorGroupsState, setInspectorGroupsState] = useState<
    "idle" | "loading" | "ready" | "error"
  >("idle");
  const [relatedPaths, setRelatedPaths] = useState<RelatedPathOption[]>([]);
  const [relatedPathsState, setRelatedPathsState] = useState<
    "idle" | "loading" | "ready" | "error"
  >("idle");

  const viewFieldNames = useMemo(() => {
    const names = new Set<string>();
    if (viewType === "form") {
      for (const child of formChildren) {
        if (child.kind === "group") {
          for (const n of child.children) {
            if (n.kind === "field") names.add(n.name);
          }
        } else {
          for (const page of child.pages) {
            for (const n of page.children) {
              if (n.kind === "field") names.add(n.name);
            }
          }
        }
      }
    } else if (viewType === "list") {
      for (const c of listColumns) names.add(c.name);
    } else if (viewType === "search") {
      for (const c of searchFields) names.add(c.name);
    } else if (viewType === "kanban") {
      for (const c of kanbanFields) names.add(c.name);
    }
    return [...names];
  }, [viewType, formChildren, listColumns, searchFields, kanbanFields]);

  const selectedFieldMeta = selectedField
    ? fields.find((f) => f.name === selectedField.name) ?? null
    : null;

  useEffect(() => {
    if (!connectionId) return;
    let cancelled = false;
    setInspectorGroupsState("loading");
    api
      .listGroups(connectionId)
      .then((rows) => {
        if (cancelled) return;
        setInspectorGroups(rows);
        setInspectorGroupsState("ready");
      })
      .catch(() => {
        if (cancelled) return;
        setInspectorGroups([]);
        setInspectorGroupsState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [connectionId]);

  useEffect(() => {
    if (!connectionId || !model) {
      setRelatedPaths([]);
      setRelatedPathsState("idle");
      return;
    }
    let cancelled = false;
    setRelatedPathsState("loading");
    api
      .listRelatedPaths(connectionId, model, 2)
      .then((rows) => {
        if (cancelled) return;
        setRelatedPaths(rows);
        setRelatedPathsState("ready");
      })
      .catch(() => {
        if (cancelled) return;
        setRelatedPaths([]);
        setRelatedPathsState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [connectionId, model]);

  useEffect(() => {
    if (!selectedField) {
      setInspectorWidgets([]);
      return;
    }
    const row = fields.find((f) => f.name === selectedField.name);
    const ttype = row?.ttype ?? "char";
    setInspectorWidgets(fallbackWidgetsForTtype(ttype));
    api
      .listBuilderWidgets(connectionId, ttype)
      .then((rows) => {
        if (rows.length > 0) setInspectorWidgets(rows);
      })
      .catch(() => {
        /* fallback */
      });
  }, [connectionId, fields, selectedField?.name]);

  const fieldInspector = selectedField ? (
    <DesignerFieldInspector
      field={{
        ...selectedField,
        ttype: selectedFieldMeta?.ttype,
      }}
      fieldMeta={selectedFieldMeta}
      widgetOptions={inspectorWidgets}
      widgetAdvanced={widgetAdvanced}
      onWidgetAdvancedChange={setWidgetAdvanced}
      onChange={updateSelectedField}
      groups={inspectorGroups}
      groupsState={inspectorGroupsState}
      relatedPaths={relatedPaths}
      relatedState={relatedPathsState}
      fieldsOnModel={fields}
      viewFieldNames={viewFieldNames}
      onAddRelatedField={(name) => appendFieldToCurrentLayout(name, fields)}
      onRemoveFromView={removeSelectedField}
    />
  ) : (
    <DesignerFieldInspectorEmpty />
  );

  return { fieldInspector };
}
