"use client";

import type { Dispatch, SetStateAction } from "react";
import type { FieldRow } from "@/lib/api";
import {
  pickTemporalDefaults,
  uid,
  type DesignerField,
  type FormChild,
  type ViewType,
} from "@/components/designer/designer-model";
export type DesignerModelLoadDeps = {
  connectionId: string;
  api: { listFields: (id: string, model: string) => Promise<FieldRow[]> };
  setError: (v: string | null) => void;
  setLoadedViewId: (v: number | null) => void;
  setLastSnapshotId: Dispatch<SetStateAction<string | null>>;
  setFields: Dispatch<SetStateAction<FieldRow[]>>;
  setFieldsModel: (v: string) => void;
  applyFieldNamesToCanvas: (names: string[], rows: FieldRow[]) => void;
  setTitle: (v: string) => void;
  viewType: ViewType;
  setFormChildren: Dispatch<SetStateAction<FormChild[]>>;
  setListColumns: Dispatch<SetStateAction<DesignerField[]>>;
  setSearchFields: Dispatch<SetStateAction<DesignerField[]>>;
  setKanbanFields: Dispatch<SetStateAction<DesignerField[]>>;
  fieldsModel: string;
  fields: FieldRow[];
  setCalendarDateStart: Dispatch<SetStateAction<string>>;
  setCalendarDateStop: Dispatch<SetStateAction<string>>;
  setGanttDateStart: Dispatch<SetStateAction<string>>;
  setGanttDateStop: Dispatch<SetStateAction<string>>;
  setCohortDateStart: Dispatch<SetStateAction<string>>;
  setCohortDateStop: Dispatch<SetStateAction<string>>;
};

export function useDesignerModelLoad(deps: DesignerModelLoadDeps) {
  const {
    connectionId,
    api,
    setError,
    setLoadedViewId,
    setLastSnapshotId,
    setFields,
    setFieldsModel,
    applyFieldNamesToCanvas,
    setTitle,
    viewType,
    setFormChildren,
    setListColumns,
    setSearchFields,
    setKanbanFields,
    fieldsModel,
    fields,
    setCalendarDateStart,
    setCalendarDateStop,
    setGanttDateStart,
    setGanttDateStop,
    setCohortDateStart,
    setCohortDateStop,
  } = deps;

  async function loadModelFields(target: string) {
    setError(null);
    setLoadedViewId(null);
    setLastSnapshotId(null);
    try {
      const rows = await api.listFields(connectionId, target);
      setFields(rows);
      setFieldsModel(target);
      applyFieldNamesToCanvas([], rows);
      setTitle(target);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load fields");
    }
  }

  /** Refresh field metadata without wiping a loaded / edited view layout. */
  async function refreshModelFieldsOnly(target: string): Promise<FieldRow[]> {
    const rows = await api.listFields(connectionId, target);
    setFields(rows);
    setFieldsModel(target);
    return rows;
  }

  function appendFieldToCurrentLayout(name: string, rows: FieldRow[]) {
    const meta = rows.find((f) => f.name === name);
    const node: DesignerField = {
      kind: "field",
      id: uid("f"),
      name,
      string: meta?.field_description,
    };
    if (viewType === "form") {
      setFormChildren((children) => {
        const already = children.some(
          (c) =>
            (c.kind === "group" &&
              c.children.some((n) => n.kind === "field" && n.name === name)) ||
            (c.kind === "notebook" &&
              c.pages.some((p) =>
                p.children.some((n) => n.kind === "field" && n.name === name),
              )),
        );
        if (already) return children;
        const firstGroupIdx = children.findIndex((c) => c.kind === "group");
        if (firstGroupIdx < 0) {
          return [
            ...children,
            { kind: "group", id: uid("g"), string: "Main", children: [node] },
          ];
        }
        return children.map((child, i) =>
          i === firstGroupIdx && child.kind === "group"
            ? { ...child, children: [...child.children, node] }
            : child,
        );
      });
      return;
    }
    if (viewType === "list") {
      setListColumns((cols) =>
        cols.some((c) => c.name === name) ? cols : [...cols, node],
      );
    } else if (viewType === "search") {
      setSearchFields((cols) =>
        cols.some((c) => c.name === name) ? cols : [...cols, node],
      );
    } else if (viewType === "kanban") {
      setKanbanFields((cols) =>
        cols.some((c) => c.name === name) ? cols : [...cols, node],
      );
    }
  }

  async function ensureFieldsForModel(target: string) {
    const trimmed = target.trim();
    if (!trimmed || !connectionId) return;
    if (fieldsModel === trimmed && fields.length > 0) return;
    try {
      const rows = await api.listFields(connectionId, trimmed);
      setFields(rows);
      setFieldsModel(trimmed);
      const { dateStart, dateStop } = pickTemporalDefaults(rows);
      setCalendarDateStart((prev) =>
        prev && rows.some((f) => f.name === prev) ? prev : dateStart,
      );
      setCalendarDateStop((prev) =>
        prev && rows.some((f) => f.name === prev) ? prev : dateStop,
      );
      setGanttDateStart((prev) =>
        prev && rows.some((f) => f.name === prev) ? prev : dateStart,
      );
      setGanttDateStop((prev) =>
        prev && rows.some((f) => f.name === prev) ? prev : dateStop,
      );
      setCohortDateStart((prev) =>
        prev && rows.some((f) => f.name === prev) ? prev : dateStart || "create_date",
      );
      setCohortDateStop((prev) =>
        prev && rows.some((f) => f.name === prev) ? prev : dateStop,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load fields");
    }
  }

  return {
    loadModelFields,
    refreshModelFieldsOnly,
    appendFieldToCurrentLayout,
    ensureFieldsForModel,
  };
}
