"use client";

import { useRef, useState } from "react";
import type {
  ActivityTypeRow,
  Connection,
  FieldRow,
  MailTemplateRow,
  PreviewTheme,
  SnapshotRow,
} from "@/lib/api";
import type { DesignerCanvasMode } from "@/components/designer/DesignerLiveCanvas";
import type { DesignerRailTabId } from "@/components/designer/DesignerToolsRail";
import type { NicheWidgetEntry } from "@/components/designer/NicheWidgetPalette";
import type { LocatorIssue } from "@/components/designer/XPathInheritPanel";
import {
  INITIAL_FORM_CHILDREN,
  type AxisDesignerField,
  type BindDialogMode,
  type ButtonPlacement,
  type DesignerButton,
  type DesignerCanvasSnapshot,
  type DesignerField,
  type FormChild,
  type SearchFilter,
  type SearchGroupByFilter,
  type SelectedField,
  type ViewType,
} from "@/components/designer/designer-model";
import { useDesignerHistory } from "@/components/designer/useDesignerHistory";

export function useDesignerPageState() {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [probing, setProbing] = useState(false);
  const [model, setModel] = useState("");
  const [viewType, setViewType] = useState<ViewType>("form");
  const [title, setTitle] = useState("Form");
  const [fields, setFields] = useState<FieldRow[]>([]);
  const [fieldsModel, setFieldsModel] = useState("");
  const [formChildren, setFormChildren] =
    useState<FormChild[]>(INITIAL_FORM_CHILDREN);
  const [listColumns, setListColumns] = useState<DesignerField[]>([]);
  const [searchFields, setSearchFields] = useState<DesignerField[]>([]);
  const [kanbanFields, setKanbanFields] = useState<DesignerField[]>([]);
  const [kanbanGroupBy, setKanbanGroupBy] = useState("");
  const [calendarDateStart, setCalendarDateStart] = useState("");
  const [calendarDateStop, setCalendarDateStop] = useState("");
  const [calendarColor, setCalendarColor] = useState("");
  const [calendarMode, setCalendarMode] = useState("");
  const [calendarFields, setCalendarFields] = useState<DesignerField[]>([]);
  const [graphType, setGraphType] = useState<"bar" | "line" | "pie">("bar");
  const [graphFields, setGraphFields] = useState<AxisDesignerField[]>([]);
  const [pivotFields, setPivotFields] = useState<AxisDesignerField[]>([]);
  const [mapResPartner, setMapResPartner] = useState("");
  const [mapRouting, setMapRouting] = useState(false);
  const [mapFields, setMapFields] = useState<DesignerField[]>([]);
  const [activityFields, setActivityFields] = useState<DesignerField[]>([]);
  const [windowActionId, setWindowActionId] = useState<number | null>(null);
  const [ganttDateStart, setGanttDateStart] = useState("");
  const [ganttDateStop, setGanttDateStop] = useState("");
  const [ganttGroupBy, setGanttGroupBy] = useState("");
  const [ganttColor, setGanttColor] = useState("");
  const [ganttProgress, setGanttProgress] = useState("");
  const [ganttDefaultScale, setGanttDefaultScale] = useState("");
  const [ganttDependencyField, setGanttDependencyField] = useState("");
  const [ganttFields, setGanttFields] = useState<DesignerField[]>([]);
  const [cohortDateStart, setCohortDateStart] = useState("");
  const [cohortDateStop, setCohortDateStop] = useState("");
  const [cohortInterval, setCohortInterval] = useState<
    "day" | "week" | "month" | "year" | ""
  >("week");
  const [cohortMode, setCohortMode] = useState<"retention" | "churn" | "">("retention");
  const [cohortTimeline, setCohortTimeline] = useState<"forward" | "backward" | "">("");
  const [cohortMeasure, setCohortMeasure] = useState("");
  const [gridRowField, setGridRowField] = useState("");
  const [gridColField, setGridColField] = useState("");
  const [gridMeasure, setGridMeasure] = useState("");
  const [gridAdjustment, setGridAdjustment] = useState("");
  const [gridDateStart, setGridDateStart] = useState("");
  const [gridDateStop, setGridDateStop] = useState("");
  const [gridFields, setGridFields] = useState<DesignerField[]>([]);
  const [formCanCreate, setFormCanCreate] = useState(true);
  const [formCanEdit, setFormCanEdit] = useState(true);
  const [formCanDelete, setFormCanDelete] = useState(true);
  const [formCanDuplicate, setFormCanDuplicate] = useState(true);
  const [listCanCreate, setListCanCreate] = useState(true);
  const [listCanEdit, setListCanEdit] = useState(true);
  const [listCanDelete, setListCanDelete] = useState(true);
  const [listMultiEdit, setListMultiEdit] = useState(false);
  const [listDefaultOrder, setListDefaultOrder] = useState("");
  const [kanbanCanCreate, setKanbanCanCreate] = useState(true);
  const [kanbanQuickCreate, setKanbanQuickCreate] = useState(true);
  const [viewSample, setViewSample] = useState(false);
  const [nicheWidgets, setNicheWidgets] = useState<NicheWidgetEntry[]>([]);
  const [colorPalette, setColorPalette] = useState<Array<{ index: number; name: string }>>(
    [],
  );
  const [previewTheme, setPreviewTheme] = useState<PreviewTheme | null>(null);
  const [searchGroupByFilters, setSearchGroupByFilters] = useState<SearchGroupByFilter[]>(
    [],
  );
  const [arch, setArch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [canvasFlashId, setCanvasFlashId] = useState<string | null>(null);
  const [toolbarFlash, setToolbarFlash] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragField, setDragField] = useState<string | null>(null);
  const [lastSnapshotId, setLastSnapshotId] = useState<string | null>(null);
  const [loadedViewId, setLoadedViewId] = useState<number | null>(null);
  const [snapshots, setSnapshots] = useState<SnapshotRow[]>([]);
  const [snapshotsHydrated, setSnapshotsHydrated] = useState(false);
  const [selected, setSelected] = useState<SelectedField | null>(null);
  const [canvasMode, setCanvasMode] = useState<DesignerCanvasMode>("live");
  const [liveFailed, setLiveFailed] = useState(false);
  const [railTab, setRailTab] = useState<DesignerRailTabId>("fields");
  const previewIframeRef = useRef<HTMLIFrameElement | null>(null);
  const [previewKey, setPreviewKey] = useState(0);
  const [saveStrategy, setSaveStrategy] = useState<"inherit" | "overwrite">("inherit");
  const [confirmOverwriteOpen, setConfirmOverwriteOpen] = useState(false);
  const [confirmUnlinkInheritOpen, setConfirmUnlinkInheritOpen] = useState(false);
  const [searchFilters, setSearchFilters] = useState<SearchFilter[]>([]);
  const [headerButtons, setHeaderButtons] = useState<DesignerButton[]>([]);
  const [buttonBox, setButtonBox] = useState<DesignerButton[]>([]);
  const [bindMode, setBindMode] = useState<BindDialogMode>("closed");
  const [bindPlacement, setBindPlacement] = useState<ButtonPlacement>("header");
  const [bindLabel, setBindLabel] = useState("Mark Available");
  const [bindFieldName, setBindFieldName] = useState("x_status");
  const [bindValue, setBindValue] = useState("available");
  const [bindTargetModel, setBindTargetModel] = useState("x_lib_loan");
  const [bindRelationField, setBindRelationField] = useState("x_book_id");
  const [bindIcon, setBindIcon] = useState("fa-list");
  const [bindableActions, setBindableActions] = useState<
    Array<{
      id: number;
      name: string;
      action_type: "ir.actions.server" | "ir.actions.act_window";
      model: string;
      detail: string | null;
    }>
  >([]);
  const [selectedActionId, setSelectedActionId] = useState<number | "">("");
  const [listDecorationDanger, setListDecorationDanger] = useState("");
  const [listDecorationInfo, setListDecorationInfo] = useState("");
  const [listDecorationMuted, setListDecorationMuted] = useState("");
  const [statusbarField, setStatusbarField] = useState("");
  const [statusbarVisible, setStatusbarVisible] = useState("");
  const [newFieldName, setNewFieldName] = useState("");
  const [newFieldLabel, setNewFieldLabel] = useState("");
  const [newFieldType, setNewFieldType] = useState("char");
  const [injectStrategy, setInjectStrategy] = useState<"inherit" | "mutate">(
    "inherit",
  );
  const [confirmMutateOpen, setConfirmMutateOpen] = useState(false);
  const [confirmPhrase, setConfirmPhrase] = useState("");
  const [bindActivityTypeId, setBindActivityTypeId] = useState<number | "">("");
  const [bindActivitySummary, setBindActivitySummary] = useState("Follow up");
  const [bindActivityNote, setBindActivityNote] = useState("");
  const [activityTypes, setActivityTypes] = useState<ActivityTypeRow[]>([]);
  const [bindMailTemplateId, setBindMailTemplateId] = useState<number | "">("");
  const [bindMailMethod, setBindMailMethod] = useState<"email" | "comment" | "note">("email");
  const [bindMailSubject, setBindMailSubject] = useState("");
  const [bindMailBody, setBindMailBody] = useState("");
  const [bindMailEmailTo, setBindMailEmailTo] = useState("");
  const [mailTemplates, setMailTemplates] = useState<MailTemplateRow[]>([]);
  const [bindCreateCountField, setBindCreateCountField] = useState(false);
  const [bindOne2manyField, setBindOne2manyField] = useState("");
  const [bindCountFieldName, setBindCountFieldName] = useState("");
  const [bindSmartConfirmPhrase, setBindSmartConfirmPhrase] = useState("");
  const [xpathExpr, setXpathExpr] = useState("//sheet");
  const [xpathPosition, setXpathPosition] = useState<
    "inside" | "after" | "before" | "replace" | "attributes"
  >("inside");
  const [xpathBody, setXpathBody] = useState('<field name="x_name"/>');
  const [xpathIssues, setXpathIssues] = useState<LocatorIssue[]>([]);
  const [xpathArchPreview, setXpathArchPreview] = useState("");
  const [xpathSuggested, setXpathSuggested] = useState<string | null>(null);
  const [xpathDefaultInject, setXpathDefaultInject] = useState<string | null>(null);
  const [xpathMatchCount, setXpathMatchCount] = useState<number | null>(null);
  const [xpathBlocking, setXpathBlocking] = useState(false);
  const [archOverride, setArchOverride] = useState<string | null>(null);
  const [editingFilterId, setEditingFilterId] = useState<string | null>(null);

  const history = useDesignerHistory<DesignerCanvasSnapshot>();
  const historySkipRef = useRef<"reset" | "apply" | null>("reset");
  const pendingCoalesceRef = useRef<string | undefined>(undefined);
  const pendingHistoryLabelRef = useRef<string | undefined>(undefined);

  return {
    connection, setConnection, probing, setProbing, model, setModel,
    viewType, setViewType, title, setTitle, fields, setFields,
    fieldsModel, setFieldsModel, formChildren, setFormChildren, listColumns, setListColumns,
    searchFields, setSearchFields, kanbanFields, setKanbanFields, kanbanGroupBy, setKanbanGroupBy,
    calendarDateStart, setCalendarDateStart, calendarDateStop, setCalendarDateStop, calendarColor, setCalendarColor,
    calendarMode, setCalendarMode, calendarFields, setCalendarFields, graphType, setGraphType,
    graphFields, setGraphFields, pivotFields, setPivotFields, mapResPartner, setMapResPartner,
    mapRouting, setMapRouting, mapFields, setMapFields, activityFields, setActivityFields,
    windowActionId, setWindowActionId, ganttDateStart, setGanttDateStart, ganttDateStop, setGanttDateStop,
    ganttGroupBy, setGanttGroupBy, ganttColor, setGanttColor, ganttProgress, setGanttProgress,
    ganttDefaultScale, setGanttDefaultScale, ganttDependencyField, setGanttDependencyField, ganttFields, setGanttFields,
    cohortDateStart, setCohortDateStart, cohortDateStop, setCohortDateStop, cohortInterval, setCohortInterval,
    cohortMode, setCohortMode, cohortTimeline, setCohortTimeline, cohortMeasure, setCohortMeasure,
    gridRowField, setGridRowField, gridColField, setGridColField, gridMeasure, setGridMeasure,
    gridAdjustment, setGridAdjustment, gridDateStart, setGridDateStart, gridDateStop, setGridDateStop,
    gridFields, setGridFields, formCanCreate, setFormCanCreate, formCanEdit, setFormCanEdit,
    formCanDelete, setFormCanDelete, formCanDuplicate, setFormCanDuplicate, listCanCreate, setListCanCreate,
    listCanEdit, setListCanEdit, listCanDelete, setListCanDelete, listMultiEdit, setListMultiEdit,
    listDefaultOrder, setListDefaultOrder, kanbanCanCreate, setKanbanCanCreate, kanbanQuickCreate, setKanbanQuickCreate,
    viewSample, setViewSample, nicheWidgets, setNicheWidgets, colorPalette, setColorPalette,
    previewTheme, setPreviewTheme, searchGroupByFilters, setSearchGroupByFilters, arch, setArch,
    error, setError, notice, setNotice, canvasFlashId, setCanvasFlashId,
    toolbarFlash, setToolbarFlash, busy, setBusy, dragField, setDragField,
    lastSnapshotId, setLastSnapshotId, loadedViewId, setLoadedViewId, snapshots, setSnapshots,
    snapshotsHydrated, setSnapshotsHydrated, selected, setSelected, canvasMode, setCanvasMode,
    liveFailed, setLiveFailed, railTab, setRailTab, previewIframeRef, previewKey,
    setPreviewKey, saveStrategy, setSaveStrategy, confirmOverwriteOpen, setConfirmOverwriteOpen, confirmUnlinkInheritOpen,
    setConfirmUnlinkInheritOpen, searchFilters, setSearchFilters, headerButtons, setHeaderButtons, buttonBox,
    setButtonBox, bindMode, setBindMode, bindPlacement, setBindPlacement, bindLabel,
    setBindLabel, bindFieldName, setBindFieldName, bindValue, setBindValue, bindTargetModel,
    setBindTargetModel, bindRelationField, setBindRelationField, bindIcon, setBindIcon, bindableActions,
    setBindableActions, selectedActionId, setSelectedActionId, listDecorationDanger, setListDecorationDanger, listDecorationInfo,
    setListDecorationInfo, listDecorationMuted, setListDecorationMuted, statusbarField, setStatusbarField, statusbarVisible,
    setStatusbarVisible, newFieldName, setNewFieldName, newFieldLabel, setNewFieldLabel, newFieldType,
    setNewFieldType, injectStrategy, setInjectStrategy, confirmMutateOpen, setConfirmMutateOpen, confirmPhrase,
    setConfirmPhrase, bindActivityTypeId, setBindActivityTypeId, bindActivitySummary, setBindActivitySummary, bindActivityNote,
    setBindActivityNote, activityTypes, setActivityTypes, bindMailTemplateId, setBindMailTemplateId, bindMailMethod,
    setBindMailMethod, bindMailSubject, setBindMailSubject, bindMailBody, setBindMailBody, bindMailEmailTo,
    setBindMailEmailTo, mailTemplates, setMailTemplates, bindCreateCountField, setBindCreateCountField, bindOne2manyField,
    setBindOne2manyField, bindCountFieldName, setBindCountFieldName, bindSmartConfirmPhrase, setBindSmartConfirmPhrase, xpathExpr,
    setXpathExpr, xpathPosition, setXpathPosition, xpathBody, setXpathBody, xpathIssues,
    setXpathIssues, xpathArchPreview, setXpathArchPreview, xpathSuggested, setXpathSuggested, xpathDefaultInject,
    setXpathDefaultInject, xpathMatchCount, setXpathMatchCount, xpathBlocking, setXpathBlocking, archOverride,
    setArchOverride, editingFilterId, setEditingFilterId, history, historySkipRef, pendingCoalesceRef,
    pendingHistoryLabelRef,
  };
}

export type DesignerPageState = ReturnType<typeof useDesignerPageState>;
