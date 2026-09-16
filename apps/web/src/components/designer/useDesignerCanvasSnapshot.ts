"use client";

import { useMemo } from "react";
import type { DesignerCanvasSnapshot } from "@/components/designer/designer-model";
import {
  applyCanvasSnapshot as applyCanvasSnapshotToState,
  type ApplyCanvasSnapshotDeps,
} from "@/components/designer/applyCanvasSnapshot";

export function useDesignerCanvasSnapshot(
  parts: DesignerCanvasSnapshot,
  setters: ApplyCanvasSnapshotDeps,
) {
  const canvasSnapshot = useMemo<DesignerCanvasSnapshot>(
    () => ({ ...parts }),
    [
      parts.title,
      parts.formChildren,
      parts.headerButtons,
      parts.buttonBox,
      parts.statusbarField,
      parts.statusbarVisible,
      parts.formCanCreate,
      parts.formCanEdit,
      parts.formCanDelete,
      parts.formCanDuplicate,
      parts.listColumns,
      parts.listDecorationDanger,
      parts.listDecorationInfo,
      parts.listDecorationMuted,
      parts.listCanCreate,
      parts.listCanEdit,
      parts.listCanDelete,
      parts.listMultiEdit,
      parts.listDefaultOrder,
      parts.viewSample,
      parts.searchFields,
      parts.searchFilters,
      parts.searchGroupByFilters,
      parts.kanbanFields,
      parts.kanbanGroupBy,
      parts.kanbanCanCreate,
      parts.kanbanQuickCreate,
      parts.calendarDateStart,
      parts.calendarDateStop,
      parts.calendarColor,
      parts.calendarMode,
      parts.calendarFields,
      parts.graphType,
      parts.graphFields,
      parts.pivotFields,
      parts.mapResPartner,
      parts.mapRouting,
      parts.mapFields,
      parts.activityFields,
      parts.ganttDateStart,
      parts.ganttDateStop,
      parts.ganttGroupBy,
      parts.ganttColor,
      parts.ganttProgress,
      parts.ganttDefaultScale,
      parts.ganttDependencyField,
      parts.ganttFields,
      parts.cohortDateStart,
      parts.cohortDateStop,
      parts.cohortInterval,
      parts.cohortMode,
      parts.cohortTimeline,
      parts.cohortMeasure,
      parts.gridRowField,
      parts.gridColField,
      parts.gridMeasure,
      parts.gridAdjustment,
      parts.gridDateStart,
      parts.gridDateStop,
      parts.gridFields,
      parts.archOverride,
    ],
  );

  function applyCanvasSnapshot(snapshot: DesignerCanvasSnapshot) {
    applyCanvasSnapshotToState(setters, snapshot);
  }

  return { canvasSnapshot, applyCanvasSnapshot };
}
