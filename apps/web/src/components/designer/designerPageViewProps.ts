import type { ComponentProps, ReactNode } from "react";
import type { FieldRow } from "@/lib/api";
import type { DesignerStudioToolbarProps } from "@/components/designer/DesignerStudioToolbar";
import type { DesignerStudioRailProps } from "@/components/designer/DesignerStudioRail";
import type { DesignerStructuralCanvasProps } from "@/components/designer/DesignerStructuralCanvas";
import {
  DesignerSessionBar,
  designerPublishState,
} from "@/components/designer/DesignerSessionBar";
import type { useDesignerCanvasMutations } from "@/components/designer/useDesignerCanvasMutations";
import type { useDesignerPersist } from "@/components/designer/useDesignerPersist";
import type { DesignerPageModel } from "@/components/designer/useDesignerPageModel";
import {
  classifyDesignerError,
  isPreviewStale,
  type DesignerCanvasState,
} from "@/components/designer/designerCanvasState";

type Mutations = ReturnType<typeof useDesignerCanvasMutations>;
type Persist = ReturnType<typeof useDesignerPersist>;
type SessionBarProps = ComponentProps<typeof DesignerSessionBar>;

export function designerSessionBarProps(
  m: DesignerPageModel,
  persist: Persist,
): SessionBarProps {
  return {
    publishState: designerPublishState({
      dirty: m.history.dirty,
      hasPublishedView: m.loadedViewId != null,
    }),
    canUndo: m.history.canUndo,
    canRedo: m.history.canRedo,
    canRollbackPublish: Boolean(m.lastSnapshotId),
    undoLabel: m.history.undoLabel,
    redoLabel: m.history.redoLabel,
    busy: m.busy,
    onUndo: persist.onSessionUndo,
    onRedo: persist.onSessionRedo,
    onRollbackPublish: () => void persist.onRollbackLastPublish(),
    onEmptyUndo: () =>
      m.setNotice(
        m.lastSnapshotId
          ? "Nothing to undo in this session. Use roll back last publish to restore a snapshot."
          : "Nothing to undo in this session. Save to Odoo first creates a published checkpoint.",
      ),
  };
}

export function designerToolbarProps(
  m: DesignerPageModel,
  persist: Persist,
  dateFieldsForSelect: FieldRow[],
): DesignerStudioToolbarProps {
  return {
    model: m.model,
    setModel: m.setModel,
    ensureFieldsForModel: m.ensureFieldsForModel,
    loadModelFields: m.loadModelFields,
    loadExistingView: m.loadExistingView,
    viewType: m.viewType,
    setViewType: m.setViewType,
    title: m.title,
    setTitle: m.setTitle,
    busy: m.busy,
    onSave: () => void persist.onSave(),
    saveStrategy: m.saveStrategy,
    setSaveStrategy: m.setSaveStrategy,
    setConfirmUnlinkInheritOpen: m.setConfirmUnlinkInheritOpen,
    loadedViewId: m.loadedViewId,
    connection: m.connection,
    connectionId: m.connectionId,
    api: m.api,
    setNotice: m.setNotice,
    setError: m.setError,
    setBusy: m.setBusy,
    setSelected: m.setSelected,
    kanbanGroupBy: m.kanbanGroupBy,
    setKanbanGroupBy: m.setKanbanGroupBy,
    fields: m.fields,
    dateFieldsForSelect,
    calendarDateStart: m.calendarDateStart,
    setCalendarDateStart: m.setCalendarDateStart,
    calendarDateStop: m.calendarDateStop,
    setCalendarDateStop: m.setCalendarDateStop,
    calendarColor: m.calendarColor,
    setCalendarColor: m.setCalendarColor,
    calendarMode: m.calendarMode,
    setCalendarMode: m.setCalendarMode,
    viewSample: m.viewSample,
    setViewSample: m.setViewSample,
    graphType: m.graphType,
    setGraphType: m.setGraphType,
    mapResPartner: m.mapResPartner,
    setMapResPartner: m.setMapResPartner,
    mapRouting: m.mapRouting,
    setMapRouting: m.setMapRouting,
    ganttDateStart: m.ganttDateStart,
    setGanttDateStart: m.setGanttDateStart,
    ganttDateStop: m.ganttDateStop,
    setGanttDateStop: m.setGanttDateStop,
    ganttGroupBy: m.ganttGroupBy,
    setGanttGroupBy: m.setGanttGroupBy,
    ganttColor: m.ganttColor,
    setGanttColor: m.setGanttColor,
    ganttProgress: m.ganttProgress,
    setGanttProgress: m.setGanttProgress,
    ganttDefaultScale: m.ganttDefaultScale,
    setGanttDefaultScale: m.setGanttDefaultScale,
    ganttDependencyField: m.ganttDependencyField,
    setGanttDependencyField: m.setGanttDependencyField,
    cohortDateStart: m.cohortDateStart,
    setCohortDateStart: m.setCohortDateStart,
    cohortDateStop: m.cohortDateStop,
    setCohortDateStop: m.setCohortDateStop,
    cohortInterval: m.cohortInterval,
    setCohortInterval: m.setCohortInterval,
    cohortMode: m.cohortMode,
    setCohortMode: m.setCohortMode,
    cohortTimeline: m.cohortTimeline,
    setCohortTimeline: m.setCohortTimeline,
    cohortMeasure: m.cohortMeasure,
    setCohortMeasure: m.setCohortMeasure,
    gridRowField: m.gridRowField,
    setGridRowField: m.setGridRowField,
    gridColField: m.gridColField,
    setGridColField: m.setGridColField,
    gridMeasure: m.gridMeasure,
    setGridMeasure: m.setGridMeasure,
    gridAdjustment: m.gridAdjustment,
    setGridAdjustment: m.setGridAdjustment,
    gridDateStart: m.gridDateStart,
    setGridDateStart: m.setGridDateStart,
    gridDateStop: m.gridDateStop,
    setGridDateStop: m.setGridDateStop,
    fieldsModel: m.fieldsModel,
    archOverride: m.archOverride,
    pendingCoalesceRef: m.pendingCoalesceRef,
    pendingHistoryLabelRef: m.pendingHistoryLabelRef,
    onRepairDuplicateChrome: persist.onRepairDuplicateChrome,
  };
}

export function designerRailProps(
  m: DesignerPageModel,
  persist: Persist,
  fieldInspector: ReactNode,
  mutations: Mutations,
): DesignerStudioRailProps {
  return {
    railTab: m.railTab,
    setRailTab: m.setRailTab,
    viewType: m.viewType,
    fields: m.fields,
    setDragField: m.setDragField,
    nicheWidgets: m.nicheWidgets,
    colorPalette: m.colorPalette,
    addNicheWidget: m.addNicheWidget,
    fieldInspector,
    formChildren: m.formChildren,
    addGroup: mutations.addGroup,
    addNotebook: mutations.addNotebook,
    proxyPreviewUrl: m.proxyPreviewUrl,
    previewIframeRef: m.previewIframeRef,
    connectionId: m.connectionId,
    model: m.model,
    setLastSnapshotId: m.setLastSnapshotId,
    setPreviewKey: m.setPreviewKey,
    setNotice: m.setNotice,
    refreshSnapshots: m.refreshSnapshots,
    xpathExpr: m.xpathExpr,
    xpathPosition: m.xpathPosition,
    xpathBody: m.xpathBody,
    xpathArchPreview: m.xpathArchPreview,
    xpathIssues: m.xpathIssues,
    xpathSuggested: m.xpathSuggested,
    xpathDefaultInject: m.xpathDefaultInject,
    xpathMatchCount: m.xpathMatchCount,
    xpathBlocking: m.xpathBlocking,
    busy: m.busy,
    archOverride: m.archOverride,
    setXpathExpr: m.setXpathExpr,
    setXpathBlocking: m.setXpathBlocking,
    setXpathPosition: m.setXpathPosition,
    setXpathBody: m.setXpathBody,
    runXpathPreview: persist.runXpathPreview,
    setArch: m.setArch,
    setArchOverride: m.setArchOverride,
    onSaveXpathInherit: persist.onSaveXpathInherit,
  };
}

export function designerStructuralProps(
  m: DesignerPageModel,
  mutations: Mutations,
): DesignerStructuralCanvasProps {
  return {
    viewType: m.viewType,
    model: m.model,
    title: m.title,
    fields: m.fields,
    previewTheme: m.previewTheme,
    formChildren: m.formChildren,
    headerButtons: m.headerButtons,
    buttonBox: m.buttonBox,
    statusbarField: m.statusbarField,
    statusbarVisible: m.statusbarVisible,
    canvasFlashId: m.canvasFlashId,
    selected: m.selected,
    setSelected: m.setSelected,
    setRailTab: m.setRailTab,
    listColumns: m.listColumns,
    listDecorationDanger: m.listDecorationDanger,
    listDecorationInfo: m.listDecorationInfo,
    listDecorationMuted: m.listDecorationMuted,
    kanbanFields: m.kanbanFields,
    kanbanGroupBy: m.kanbanGroupBy,
    setKanbanFields: m.setKanbanFields,
    selectCanvasField: mutations.selectCanvasField,
    addFieldToGroup: mutations.addFieldToGroup,
    dropFieldOnPage: mutations.dropFieldOnPage,
    reorderFormNode: mutations.reorderFormNode,
    setFormChildren: m.setFormChildren,
    moveKanbanField: mutations.moveKanbanField,
    addKanbanField: mutations.addKanbanField,
  };
}

/** UI-S-12: one canvas state at a time. Save errors outrank a stale preview. */
export function designerCanvasStateFor(m: DesignerPageModel): DesignerCanvasState | null {
  const errorState = classifyDesignerError(m.error);
  if (errorState) {
    return {
      ...errorState,
      action: { label: "Open Advanced", onClick: () => m.setRailTab("advanced") },
    };
  }
  if (
    isPreviewStale({
      mode: m.canvasMode,
      liveAvailable: Boolean(m.proxyPreviewUrl) && !m.liveFailed,
      dirty: m.history.dirty,
    })
  ) {
    return {
      kind: "preview-stale",
      action: { label: "Show layout canvas", onClick: () => m.setCanvasMode("structure") },
    };
  }
  return null;
}

export function designerLiveCanvasHandlers(m: DesignerPageModel) {
  return {
    canvasState: designerCanvasStateFor(m),
    mode: m.canvasMode,
    onModeChange: m.setCanvasMode,
    liveUrl: m.proxyPreviewUrl,
    iframeRef: m.previewIframeRef,
    iframeKey: m.previewKey,
    liveFailed: m.liveFailed,
    onLiveError: () => m.setLiveFailed(true),
    onRefreshLive: () => {
      m.setLiveFailed(false);
      m.setCanvasMode("live");
      m.setPreviewKey((k) => k + 1);
      m.setNotice("Preview refreshed. Open in Odoo remains authoritative.");
    },
    openInOdooUrl: m.liveOdooUrl,
  };
}
