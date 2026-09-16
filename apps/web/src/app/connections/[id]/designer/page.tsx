"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { DomainBuilder } from "@/components/DomainBuilder";
import { CapabilityProbePanel } from "@/components/CapabilityProbePanel";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { FirstWriteInterstitial } from "@/components/shell/FirstWriteInterstitial";
import { FormCanvas } from "@/components/designer/FormCanvas";
import { DesignerStudioShell } from "@/components/designer/DesignerStudioShell";
import {
  DesignerLiveCanvas,
  type DesignerCanvasMode,
} from "@/components/designer/DesignerLiveCanvas";
import { DesignerStudioRail } from "@/components/designer/DesignerStudioRail";
import { DesignerStructuralCanvas } from "@/components/designer/DesignerStructuralCanvas";
import { useDesignerViewSpecs } from "@/components/designer/useDesignerViewSpecs";
import { useDesignerCanvasMutations } from "@/components/designer/useDesignerCanvasMutations";
import { useDesignerPersist } from "@/components/designer/useDesignerPersist";
import { useDesignerModelLoad } from "@/components/designer/useDesignerModelLoad";
import { useDesignerFieldOps } from "@/components/designer/useDesignerFieldOps";
import { DesignerStudioToolbar } from "@/components/designer/DesignerStudioToolbar";
import type { DesignerRailTabId } from "@/components/designer/DesignerToolsRail";
import { FieldPalette } from "@/components/designer/FieldPalette";
import { Disclosure } from "@/components/ui/Disclosure";
import {
  OdooControlPanel,
  OdooKanbanView,
  OdooListView,
  OdooPreviewScope,
} from "@/components/odoo-preview";
import { OverlayEditor } from "@/components/designer/OverlayEditor";
import { insertAt } from "@/lib/designer-dnd";
import { KanbanCardPreview } from "@/components/designer/KanbanCardPreview";
import {
  NicheWidgetPalette,
  type NicheWidgetEntry,
} from "@/components/designer/NicheWidgetPalette";
import { PreviewThemeScope } from "@/components/designer/PreviewThemeScope";
import {
  ActivityTypeRow,
  api,
  Connection,
  FieldRow,
  MailTemplateRow,
  PreviewTheme,
  SnapshotRow,
} from "@/lib/api";
import { useDesignerFieldInspector } from "@/components/designer/useDesignerFieldInspector";
import { useDesignerCanvasSnapshot } from "@/components/designer/useDesignerCanvasSnapshot";
import { useDesignerPageBootstrap } from "@/components/designer/useDesignerPageBootstrap";
import { DesignerReportingFieldsPanel } from "@/components/designer/DesignerReportingFieldsPanel";
import { XPathInheritPanel, type LocatorIssue } from "@/components/designer/XPathInheritPanel";
import {
  DesignerSessionBar,
  designerPublishState,
} from "@/components/designer/DesignerSessionBar";
import { useDesignerHistory } from "@/components/designer/useDesignerHistory";
import { automationsHref } from "@/lib/automationForm";
import { useSyncShellContext } from "@/lib/use-sync-shell-context";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Callout } from "@/components/ui/Callout";
import { Card } from "@/components/ui/layout-primitives";

import type {
  ViewType,
  AxisDesignerField,
  DesignerField,
  DesignerButton,
  DesignerGroup,
  DesignerPage,
  DesignerNotebook,
  FormChild,
  ButtonPlacement,
  BindDialogMode,
  SearchFilter,
  SearchGroupByFilter,
  DesignerCanvasSnapshot,
  SelectedField,
} from "@/components/designer/designer-model";
import {
  uid,
  INITIAL_FORM_CHILDREN,
} from "@/components/designer/designer-model";
import {
  applyFieldNamesToCanvas as runApplyFieldNamesToCanvas,
  loadExistingView as runLoadExistingView,
} from "@/components/designer/loadExistingView";
import { DesignerUiProvider } from "@/components/designer/DesignerUiContext";
import { DesignerBindPanel } from "@/components/designer/DesignerBindPanel";
import { DesignerDangerConfirms } from "@/components/designer/DesignerDangerConfirms";
import { DesignerAdvancedFieldsAside } from "@/components/designer/DesignerAdvancedFieldsAside";
import { DesignerAdvancedMetaAside } from "@/components/designer/DesignerAdvancedMetaAside";
import { DesignerAdvancedStructureCanvas } from "@/components/designer/DesignerAdvancedStructureCanvas";

const CONFIRM_PHRASE = "I understand the risks";

export default function DesignerPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [probing, setProbing] = useState(false);
  const [model, setModel] = useState("");
  const [viewType, setViewType] = useState<ViewType>("form");
  useSyncShellContext({ model, viewType });
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

  const { canvasSnapshot, applyCanvasSnapshot } = useDesignerCanvasSnapshot(
    {
    title,
    formChildren,
    headerButtons,
    buttonBox,
    statusbarField,
    statusbarVisible,
    formCanCreate,
    formCanEdit,
    formCanDelete,
    formCanDuplicate,
    listColumns,
    listDecorationDanger,
    listDecorationInfo,
    listDecorationMuted,
    listCanCreate,
    listCanEdit,
    listCanDelete,
    listMultiEdit,
    listDefaultOrder,
    viewSample,
    searchFields,
    searchFilters,
    searchGroupByFilters,
    kanbanFields,
    kanbanGroupBy,
    kanbanCanCreate,
    kanbanQuickCreate,
    calendarDateStart,
    calendarDateStop,
    calendarColor,
    calendarMode,
    calendarFields,
    graphType,
    graphFields,
    pivotFields,
    mapResPartner,
    mapRouting,
    mapFields,
    activityFields,
    ganttDateStart,
    ganttDateStop,
    ganttGroupBy,
    ganttColor,
    ganttProgress,
    ganttDefaultScale,
    ganttDependencyField,
    ganttFields,
    cohortDateStart,
    cohortDateStop,
    cohortInterval,
    cohortMode,
    cohortTimeline,
    cohortMeasure,
    gridRowField,
    gridColField,
    gridMeasure,
    gridAdjustment,
    gridDateStart,
    gridDateStop,
    gridFields,
    archOverride
    },
    {
    setTitle,
    setFormChildren,
    setHeaderButtons,
    setButtonBox,
    setStatusbarField,
    setStatusbarVisible,
    setFormCanCreate,
    setFormCanEdit,
    setFormCanDelete,
    setFormCanDuplicate,
    setListColumns,
    setListDecorationDanger,
    setListDecorationInfo,
    setListDecorationMuted,
    setListCanCreate,
    setListCanEdit,
    setListCanDelete,
    setListMultiEdit,
    setListDefaultOrder,
    setViewSample,
    setSearchFields,
    setSearchFilters,
    setSearchGroupByFilters,
    setKanbanFields,
    setKanbanGroupBy,
    setKanbanCanCreate,
    setKanbanQuickCreate,
    setCalendarDateStart,
    setCalendarDateStop,
    setCalendarColor,
    setCalendarMode,
    setCalendarFields,
    setGraphType,
    setGraphFields,
    setPivotFields,
    setMapResPartner,
    setMapRouting,
    setMapFields,
    setActivityFields,
    setGanttDateStart,
    setGanttDateStop,
    setGanttGroupBy,
    setGanttColor,
    setGanttProgress,
    setGanttDefaultScale,
    setGanttDependencyField,
    setGanttFields,
    setCohortDateStart,
    setCohortDateStop,
    setCohortInterval,
    setCohortMode,
    setCohortTimeline,
    setCohortMeasure,
    setGridRowField,
    setGridColField,
    setGridMeasure,
    setGridAdjustment,
    setGridDateStart,
    setGridDateStop,
    setGridFields,
    setArchOverride
    },
  );



  useEffect(() => {
    const skip = historySkipRef.current;
    if (skip === "reset") {
      history.reset(canvasSnapshot);
      historySkipRef.current = null;
      return;
    }
    if (skip === "apply") {
      historySkipRef.current = null;
      return;
    }
    history.record(canvasSnapshot, {
      label: pendingHistoryLabelRef.current,
      coalesceKey: pendingCoalesceRef.current,
    });
    pendingHistoryLabelRef.current = undefined;
    pendingCoalesceRef.current = undefined;
  }, [canvasSnapshot, history.record, history.reset]);

  const {
    refreshSnapshots,
    announceAction,
    liveOdooUrl,
    proxyPreviewUrl,
  } = useDesignerPageBootstrap({
    connectionId,
    api,
    viewType,
    model,
    setModel,
    connection,
    setConnection,
    setError,
    setNotice,
    setPreviewTheme,
    setNicheWidgets,
    setColorPalette,
    setSnapshots,
    canvasFlashId,
    setCanvasFlashId,
    toolbarFlash,
    setToolbarFlash,
    setWindowActionId,
    windowActionId,
    previewKey,
    setLiveFailed,
  });


  function applyFieldNamesToCanvas(names: string[], rows: FieldRow[]) {
    runApplyFieldNamesToCanvas(
      {
        historySkipRef,
        setFormChildren,
        setListColumns,
        setSearchFields,
        setKanbanFields,
        setCalendarFields,
        setMapFields,
        setActivityFields,
        setGanttFields,
        setGridFields,
        setCalendarDateStart,
        setCalendarDateStop,
        setCalendarColor,
        setCalendarMode,
        setGanttDateStart,
        setGanttDateStop,
        setGanttGroupBy,
        setGanttColor,
        setGanttProgress,
        setGanttDefaultScale,
        setGanttDependencyField,
        setCohortDateStart,
        setCohortDateStop,
        setCohortInterval,
        setCohortMode,
        setCohortTimeline,
        setCohortMeasure,
        setMapResPartner,
        setMapRouting,
        setFormCanCreate,
        setFormCanEdit,
        setFormCanDelete,
        setFormCanDuplicate,
        setListCanCreate,
        setListCanEdit,
        setListCanDelete,
        setListMultiEdit,
        setListDefaultOrder,
        setKanbanCanCreate,
        setKanbanQuickCreate,
        setSearchFilters,
        setSearchGroupByFilters,
        setGraphFields,
        setGraphType,
        setPivotFields,
        setGridRowField,
        setGridColField,
        setGridMeasure,
        setGridAdjustment,
        setGridDateStart,
        setGridDateStop,
        setSelected,
      },
      names,
      rows,
    );
  }

  const {
    loadModelFields,
    refreshModelFieldsOnly,
    appendFieldToCurrentLayout,
    ensureFieldsForModel,
  } = useDesignerModelLoad({
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
  });


  async function loadExistingView() {
    await runLoadExistingView({
      model,
      viewType,
      connectionId,
      api,
      historySkipRef,
      setBusy,
      setError,
      setNotice,
      setFields,
      setFieldsModel,
      setLoadedViewId,
      setArch,
      setXpathExpr,
      setTitle,
      setSelected,
      setFormChildren,
      setHeaderButtons,
      setButtonBox,
      setStatusbarField,
      setStatusbarVisible,
      setFormCanCreate,
      setFormCanEdit,
      setFormCanDelete,
      setFormCanDuplicate,
      setListColumns,
      setListDecorationDanger,
      setListDecorationInfo,
      setListDecorationMuted,
      setListCanCreate,
      setListCanEdit,
      setListCanDelete,
      setListMultiEdit,
      setListDefaultOrder,
      setViewSample,
      setSearchFields,
      setSearchFilters,
      setSearchGroupByFilters,
      setKanbanFields,
      setKanbanGroupBy,
      setKanbanCanCreate,
      setKanbanQuickCreate,
      setCalendarDateStart,
      setCalendarDateStop,
      setCalendarColor,
      setCalendarMode,
      setCalendarFields,
      setGraphType,
      setGraphFields,
      setPivotFields,
      setMapResPartner,
      setMapRouting,
      setMapFields,
      setActivityFields,
      setGanttDateStart,
      setGanttDateStop,
      setGanttGroupBy,
      setGanttColor,
      setGanttProgress,
      setGanttDefaultScale,
      setGanttDependencyField,
      setGanttFields,
      setCohortDateStart,
      setCohortDateStop,
      setCohortInterval,
      setCohortMode,
      setCohortTimeline,
      setCohortMeasure,
      setGridRowField,
      setGridColField,
      setGridMeasure,
      setGridAdjustment,
      setGridDateStart,
      setGridDateStop,
      setGridFields,
    });
  }

  const {
    formSpec,
    listSpec,
    searchSpec,
    kanbanSpec,
    calendarSpec,
    dateFieldsForSelect,
    graphSpec,
    pivotSpec,
    mapSpec,
    activitySpec,
    ganttSpec,
    gridSpec,
    cohortSpec,
    activeViewSpec,
  } = useDesignerViewSpecs({
    viewType,
    title,
    fields,
    formChildren,
    headerButtons,
    buttonBox,
    statusbarField,
    statusbarVisible,
    formCanCreate,
    formCanEdit,
    formCanDelete,
    formCanDuplicate,
    listColumns,
    listDecorationDanger,
    listDecorationInfo,
    listDecorationMuted,
    listCanCreate,
    listCanEdit,
    listCanDelete,
    listMultiEdit,
    listDefaultOrder,
    viewSample,
    searchFields,
    searchFilters,
    searchGroupByFilters,
    kanbanFields,
    kanbanGroupBy,
    kanbanCanCreate,
    kanbanQuickCreate,
    calendarDateStart,
    calendarDateStop,
    calendarColor,
    calendarMode,
    calendarFields,
    graphType,
    graphFields,
    pivotFields,
    mapResPartner,
    mapRouting,
    mapFields,
    activityFields,
    ganttDateStart,
    ganttDateStop,
    ganttGroupBy,
    ganttColor,
    ganttProgress,
    ganttDefaultScale,
    ganttDependencyField,
    ganttFields,
    gridRowField,
    gridColField,
    gridMeasure,
    gridAdjustment,
    gridDateStart,
    gridDateStop,
    gridFields,
    cohortDateStart,
    cohortDateStop,
    cohortInterval,
    cohortMode,
    cohortTimeline,
    cohortMeasure,
  });

  const refreshPreview = useCallback(async () => {
    if (!model) return;
    try {
      const res = await api.previewViewArch(connectionId, viewType, activeViewSpec);
      setArch(res.arch);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Preview failed");
    }
  }, [connectionId, activeViewSpec, model, viewType]);

  useEffect(() => {
    refreshPreview();
  }, [refreshPreview]);

  const {
    moveKanbanField,
    findSelectedField,
    removeSelectedField,
    updateSelectedField,
    addGroup,
    addNotebook,
    addPageToNotebook,
    removeFormChild,
    removeNotebookPage,
    renameNotebookPage,
    renameGroup,
    openBindDialog,
    placeBoundButton,
    submitBindDialog,
    addButtonToFirstGroup,
    resolveDragFieldName,
    addFieldToGroup,
    dropOnGroup,
    dropOnPage,
    dropFieldOnPage,
    reorderFormNode,
    selectCanvasField,
    addListColumn,
    addSearchField,
    addKanbanField,
  } = useDesignerCanvasMutations({
    model,
    connectionId,
    connection,
    selected,
    setSelected,
    setRailTab,
    formChildren,
    setFormChildren,
    listColumns,
    setListColumns,
    searchFields,
    setSearchFields,
    kanbanFields,
    setKanbanFields,
    headerButtons,
    setHeaderButtons,
    buttonBox,
    setButtonBox,
    setBusy,
    setError,
    setNotice,
    pendingCoalesceRef,
    pendingHistoryLabelRef,
    dragField,
    setDragField,
    bindMode,
    setBindMode,
    bindPlacement,
    setBindPlacement,
    bindLabel,
    setBindLabel,
    bindFieldName,
    bindValue,
    bindTargetModel,
    bindRelationField,
    bindIcon,
    bindCreateCountField,
    bindOne2manyField,
    bindCountFieldName,
    bindSmartConfirmPhrase,
    setBindSmartConfirmPhrase,
    selectedActionId,
    bindActivityTypeId,
    bindActivitySummary,
    bindActivityNote,
    bindMailTemplateId,
    bindMailMethod,
    bindMailSubject,
    bindMailBody,
    bindMailEmailTo,
    fields,
    setBindableActions,
    setSelectedActionId,
    setActivityTypes,
    setBindActivityTypeId,
    setMailTemplates,
    setBindMailTemplateId,
    api,
    announceAction,
  });

  const {
    addNicheWidget,
    removeFormField,
    createNewFieldWithInject,
  } = useDesignerFieldOps({
    model,
    connectionId,
    connection,
    viewType,
    api,
    fields,
    setFields,
    setFieldsModel,
    setBusy,
    setError,
    setNotice,
    confirmPhrase,
    setConfirmPhrase,
    injectStrategy,
    newFieldName,
    setNewFieldName,
    newFieldLabel,
    newFieldType,
    formChildren,
    setFormChildren,
    listColumns,
    setListColumns,
    kanbanFields,
    setKanbanFields,
    setSelected,
    announceAction,
    appendFieldToCurrentLayout,
    refreshModelFieldsOnly,
    setConfirmMutateOpen,
  });


  const {
    onSave,
    onRepairDuplicateChrome,
    onUnlinkDesignerInherit,
    runXpathPreview,
    onSaveXpathInherit,
    onSessionUndo,
    onSessionRedo,
    onRollbackLastPublish,
    onRollback,
  } = useDesignerPersist({
    model,
    connectionId,
    connection,
    viewType,
    title,
    saveStrategy,
    setSaveStrategy,
    archOverride,
    setArchOverride,
    activeViewSpec,
    canvasSnapshot,
    history,
    historySkipRef,
    loadedViewId,
    setLoadedViewId,
    lastSnapshotId,
    setLastSnapshotId,
    setBusy,
    setError,
    setNotice,
    setConfirmOverwriteOpen,
    setArch,
    arch,
    xpathExpr,
    xpathPosition,
    xpathBody,
    setXpathIssues,
    setXpathDefaultInject,
    setXpathArchPreview,
    setXpathSuggested,
    setXpathMatchCount,
    setXpathBlocking,
    setConfirmUnlinkInheritOpen,
    applyCanvasSnapshot,
    setPreviewKey,
    refreshSnapshots,
    loadExistingView,
    announceAction,
    api,
  });

  const selectedField = findSelectedField();

  const { fieldInspector } = useDesignerFieldInspector({
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
  });


  const structuralCanvas = (
    <DesignerStructuralCanvas
      viewType={viewType}
      model={model}
      title={title}
      fields={fields}
      previewTheme={previewTheme}
      formChildren={formChildren}
      headerButtons={headerButtons}
      buttonBox={buttonBox}
      statusbarField={statusbarField}
      statusbarVisible={statusbarVisible}
      canvasFlashId={canvasFlashId}
      selected={selected}
      setSelected={setSelected}
      setRailTab={setRailTab}
      listColumns={listColumns}
      listDecorationDanger={listDecorationDanger}
      listDecorationInfo={listDecorationInfo}
      listDecorationMuted={listDecorationMuted}
      kanbanFields={kanbanFields}
      kanbanGroupBy={kanbanGroupBy}
      setKanbanFields={setKanbanFields}
      selectCanvasField={selectCanvasField}
      addFieldToGroup={addFieldToGroup}
      dropFieldOnPage={dropFieldOnPage}
      reorderFormNode={reorderFormNode}
      setFormChildren={setFormChildren}
      moveKanbanField={moveKanbanField}
      addKanbanField={addKanbanField}
    />
  );

  return (
    <DesignerUiProvider
      selected={selected}
      setSelected={setSelected}
      railTab={railTab}
      setRailTab={setRailTab}
      designerV2Shell
    >
    <DesignerStudioShell
      title="View designer"
      description={`${connection?.name ?? connectionId} · drag onto the live or layout canvas · Save to Odoo publishes an inherit view`}
      sessionBar={
      <DesignerSessionBar
        publishState={designerPublishState({
          dirty: history.dirty,
          hasPublishedView: loadedViewId != null,
        })}
        canUndo={history.canUndo}
        canRedo={history.canRedo}
        canRollbackPublish={Boolean(lastSnapshotId)}
        undoLabel={history.undoLabel}
        redoLabel={history.redoLabel}
        busy={busy}
        onUndo={onSessionUndo}
        onRedo={onSessionRedo}
        onRollbackPublish={() => void onRollbackLastPublish()}
        onEmptyUndo={() =>
          setNotice(
            lastSnapshotId
              ? "Nothing to undo in this session. Use roll back last publish to restore a snapshot."
              : "Nothing to undo in this session. Save to Odoo first creates a published checkpoint.",
          )
        }
      />
      }
      notices={
        <>
      {connection ? <FirstWriteInterstitial connection={connection} /> : null}
      <p className="mt-2 text-sm text-muted">
        Removing a field from the view does not delete the database column.{" "}
        <Link
          href={automationsHref(connectionId, model)}
          className="text-accent hover:underline"
          data-testid="designer-automations-link"
        >
          Open automations for this model
        </Link>
        .
      </p>
      <VersionAwarenessBanner capabilities={connection?.capabilities} />
        <CapabilityProbePanel
          capabilities={connection?.capabilities}
          defaultOpen={false}
          className="mt-2"
          refreshing={probing}
          onRefresh={() => {
            void (async () => {
              setProbing(true);
              setError(null);
              try {
                const result = await api.probeConnection(connectionId);
                setConnection((prev) =>
                  prev
                    ? {
                        ...prev,
                        server_version: result.server_version,
                        capabilities: result.capabilities,
                      }
                    : prev,
                );
              } catch (err) {
                setError(err instanceof Error ? err.message : "Probe failed");
              } finally {
                setProbing(false);
              }
            })();
          }}
        />
        {error ? <ErrorNotice message={error} className="mt-2" /> : null}
        {notice ? (
          <Callout variant="info" title="Notice" className="mt-2">
            {notice}
          </Callout>
        ) : null}
        </>
      }
      toolbar={
        <DesignerStudioToolbar
          model={model}
          setModel={setModel}
          ensureFieldsForModel={ensureFieldsForModel}
          loadModelFields={loadModelFields}
          loadExistingView={loadExistingView}
          viewType={viewType}
          setViewType={setViewType}
          title={title}
          setTitle={setTitle}
          busy={busy}
          onSave={() => void onSave()}
          saveStrategy={saveStrategy}
          setSaveStrategy={setSaveStrategy}
          setConfirmUnlinkInheritOpen={setConfirmUnlinkInheritOpen}
          loadedViewId={loadedViewId}
          connection={connection}
          connectionId={connectionId}
          api={api}
          setNotice={setNotice}
          setError={setError}
          setBusy={setBusy}
          setSelected={setSelected}
          kanbanGroupBy={kanbanGroupBy}
          setKanbanGroupBy={setKanbanGroupBy}
          fields={fields}
          dateFieldsForSelect={dateFieldsForSelect}
          calendarDateStart={calendarDateStart}
          setCalendarDateStart={setCalendarDateStart}
          calendarDateStop={calendarDateStop}
          setCalendarDateStop={setCalendarDateStop}
          calendarColor={calendarColor}
          setCalendarColor={setCalendarColor}
          calendarMode={calendarMode}
          setCalendarMode={setCalendarMode}
          viewSample={viewSample}
          setViewSample={setViewSample}
          graphType={graphType}
          setGraphType={setGraphType}
          mapResPartner={mapResPartner}
          setMapResPartner={setMapResPartner}
          mapRouting={mapRouting}
          setMapRouting={setMapRouting}
          ganttDateStart={ganttDateStart}
          setGanttDateStart={setGanttDateStart}
          ganttDateStop={ganttDateStop}
          setGanttDateStop={setGanttDateStop}
          ganttGroupBy={ganttGroupBy}
          setGanttGroupBy={setGanttGroupBy}
          ganttColor={ganttColor}
          setGanttColor={setGanttColor}
          ganttProgress={ganttProgress}
          setGanttProgress={setGanttProgress}
          ganttDefaultScale={ganttDefaultScale}
          setGanttDefaultScale={setGanttDefaultScale}
          ganttDependencyField={ganttDependencyField}
          setGanttDependencyField={setGanttDependencyField}
          cohortDateStart={cohortDateStart}
          setCohortDateStart={setCohortDateStart}
          cohortDateStop={cohortDateStop}
          setCohortDateStop={setCohortDateStop}
          cohortInterval={cohortInterval}
          setCohortInterval={setCohortInterval}
          cohortMode={cohortMode}
          setCohortMode={setCohortMode}
          cohortTimeline={cohortTimeline}
          setCohortTimeline={setCohortTimeline}
          cohortMeasure={cohortMeasure}
          setCohortMeasure={setCohortMeasure}
          gridRowField={gridRowField}
          setGridRowField={setGridRowField}
          gridColField={gridColField}
          setGridColField={setGridColField}
          gridMeasure={gridMeasure}
          setGridMeasure={setGridMeasure}
          gridAdjustment={gridAdjustment}
          setGridAdjustment={setGridAdjustment}
          gridDateStart={gridDateStart}
          setGridDateStart={setGridDateStart}
          gridDateStop={gridDateStop}
          setGridDateStop={setGridDateStop}
          fieldsModel={fieldsModel}
          archOverride={archOverride}
          pendingCoalesceRef={pendingCoalesceRef}
          pendingHistoryLabelRef={pendingHistoryLabelRef}
          onRepairDuplicateChrome={onRepairDuplicateChrome}
        />
      }
      canvas={
        <DesignerLiveCanvas
          mode={canvasMode}
          onModeChange={setCanvasMode}
          liveUrl={proxyPreviewUrl}
          iframeRef={previewIframeRef}
          iframeKey={previewKey}
          liveFailed={liveFailed}
          onLiveError={() => setLiveFailed(true)}
          onRefreshLive={() => {
            setLiveFailed(false);
            setCanvasMode("live");
            setPreviewKey((k) => k + 1);
            setNotice("Preview refreshed. Open in Odoo remains authoritative.");
          }}
          openInOdooUrl={liveOdooUrl}
          structural={structuralCanvas}
        />
      }
      rail={
        <DesignerStudioRail
          railTab={railTab}
          setRailTab={setRailTab}
          viewType={viewType}
          fields={fields}
          setDragField={setDragField}
          nicheWidgets={nicheWidgets}
          colorPalette={colorPalette}
          addNicheWidget={addNicheWidget}
          fieldInspector={fieldInspector}
          formChildren={formChildren}
          addGroup={addGroup}
          addNotebook={addNotebook}
          proxyPreviewUrl={proxyPreviewUrl}
          previewIframeRef={previewIframeRef}
          connectionId={connectionId}
          model={model}
          setLastSnapshotId={setLastSnapshotId}
          setPreviewKey={setPreviewKey}
          setNotice={setNotice}
          refreshSnapshots={refreshSnapshots}
          xpathExpr={xpathExpr}
          xpathPosition={xpathPosition}
          xpathBody={xpathBody}
          xpathArchPreview={xpathArchPreview}
          xpathIssues={xpathIssues}
          xpathSuggested={xpathSuggested}
          xpathDefaultInject={xpathDefaultInject}
          xpathMatchCount={xpathMatchCount}
          xpathBlocking={xpathBlocking}
          busy={busy}
          archOverride={archOverride}
          setXpathExpr={setXpathExpr}
          setXpathBlocking={setXpathBlocking}
          setXpathPosition={setXpathPosition}
          setXpathBody={setXpathBody}
          runXpathPreview={runXpathPreview}
          setArch={setArch}
          setArchOverride={setArchOverride}
          onSaveXpathInherit={onSaveXpathInherit}
        />
      }
      extras={
        <>
        <Callout variant="info" title="Production defaults" className="mx-4 mt-4 md:mx-6">
          <details>
            <summary className="cursor-pointer text-sm text-muted">
              Show save / button / preview notes
            </summary>
            <ul className="mt-2 list-disc space-y-1 pl-4 text-sm">
              <li>
                Save strategy defaults to <strong>Inherit</strong> (extension view) — safe for
                installed modules.
              </li>
              <li>
                On stock models (e.g. <code>account.move</code>), Inherit saves only{" "}
                <strong>new custom fields/groups</strong> — it does not re-emit Send/Print/Pay or
                notebook tabs (that caused duplicates on Bills).
              </li>
              <li>
                Vendor bills open as <strong>Bills</strong> in Odoo; customer invoices as{" "}
                <strong>Invoices</strong> — same model <code>account.move</code>.
              </li>
              <li>
                <strong>Overwrite</strong> requires confirm and snapshots the primary view first.
              </li>
              <li>
                Buttons bind to real <code>ir.actions.server</code> /{" "}
                <code>ir.actions.act_window</code> (type=action). Python object methods need Option A.
              </li>
              <li>
                Prefer <strong>Open in Odoo</strong> for truth; iframe preview is best-effort via
                authenticated proxy.
              </li>
              <li>
                Create field requires the confirm phrase and injects via inherit xpath.
              </li>
            </ul>
          </details>
        </Callout>

        <DesignerReportingFieldsPanel
          viewType={viewType}
          model={model}
          fields={fields}
          calendarFields={calendarFields}
          setCalendarFields={setCalendarFields}
          mapFields={mapFields}
          setMapFields={setMapFields}
          activityFields={activityFields}
          setActivityFields={setActivityFields}
          ganttFields={ganttFields}
          setGanttFields={setGanttFields}
          gridFields={gridFields}
          setGridFields={setGridFields}
          graphFields={graphFields}
          setGraphFields={setGraphFields}
          pivotFields={pivotFields}
          setPivotFields={setPivotFields}
        />


        {bindMode !== "closed" && (
          <DesignerBindPanel
            connection={connection}
            fields={fields}
            bindMode={bindMode}
            bindPlacement={bindPlacement}
            bindLabel={bindLabel}
            setBindLabel={setBindLabel}
            bindFieldName={bindFieldName}
            setBindFieldName={setBindFieldName}
            bindValue={bindValue}
            setBindValue={setBindValue}
            bindTargetModel={bindTargetModel}
            setBindTargetModel={setBindTargetModel}
            bindRelationField={bindRelationField}
            setBindRelationField={setBindRelationField}
            bindIcon={bindIcon}
            setBindIcon={setBindIcon}
            bindCreateCountField={bindCreateCountField}
            setBindCreateCountField={setBindCreateCountField}
            bindOne2manyField={bindOne2manyField}
            setBindOne2manyField={setBindOne2manyField}
            bindCountFieldName={bindCountFieldName}
            setBindCountFieldName={setBindCountFieldName}
            bindSmartConfirmPhrase={bindSmartConfirmPhrase}
            setBindSmartConfirmPhrase={setBindSmartConfirmPhrase}
            selectedActionId={selectedActionId}
            setSelectedActionId={setSelectedActionId}
            bindableActions={bindableActions}
            activityTypes={activityTypes}
            mailTemplates={mailTemplates}
            bindActivityTypeId={bindActivityTypeId}
            setBindActivityTypeId={setBindActivityTypeId}
            bindActivitySummary={bindActivitySummary}
            setBindActivitySummary={setBindActivitySummary}
            bindActivityNote={bindActivityNote}
            setBindActivityNote={setBindActivityNote}
            bindMailTemplateId={bindMailTemplateId}
            setBindMailTemplateId={setBindMailTemplateId}
            bindMailMethod={bindMailMethod}
            setBindMailMethod={setBindMailMethod}
            bindMailSubject={bindMailSubject}
            setBindMailSubject={setBindMailSubject}
            bindMailBody={bindMailBody}
            setBindMailBody={setBindMailBody}
            bindMailEmailTo={bindMailEmailTo}
            setBindMailEmailTo={setBindMailEmailTo}
            busy={busy}
            confirmPhrase={CONFIRM_PHRASE}
            openBindDialog={openBindDialog}
            onSubmitBind={(opts) => void submitBindDialog(opts)}
            onClose={() => setBindMode("closed")}
          />
        )}

        <Disclosure title="Advanced layout & field inject" testId="designer-advanced-layout" className="mx-4 mb-4 md:mx-6">
        <div className="grid gap-6 lg:grid-cols-[220px_1fr_280px]">
          <DesignerAdvancedFieldsAside
            connection={connection}
            model={model}
            viewType={viewType}
            fields={fields}
            newFieldName={newFieldName}
            setNewFieldName={setNewFieldName}
            newFieldLabel={newFieldLabel}
            setNewFieldLabel={setNewFieldLabel}
            newFieldType={newFieldType}
            setNewFieldType={setNewFieldType}
            injectStrategy={injectStrategy}
            setInjectStrategy={setInjectStrategy}
            confirmPhrase={confirmPhrase}
            setConfirmPhrase={setConfirmPhrase}
            busy={busy}
            setDragField={setDragField}
            addListColumn={addListColumn}
            addSearchField={addSearchField}
            addKanbanField={addKanbanField}
            nicheWidgets={nicheWidgets}
            colorPalette={colorPalette}
            onCreateAndInject={(opts) => void createNewFieldWithInject(opts)}
            onPickNicheWidget={(w) => void addNicheWidget(w)}
          />


          <DesignerAdvancedStructureCanvas
            viewType={viewType}
            connection={connection}
            model={model}
            title={title}
            toolbarFlash={toolbarFlash}
            canvasFlashId={canvasFlashId}
            previewTheme={previewTheme}
            viewSample={viewSample}
            setViewSample={setViewSample}
            formChildren={formChildren}
            headerButtons={headerButtons}
            buttonBox={buttonBox}
            setHeaderButtons={setHeaderButtons}
            setButtonBox={setButtonBox}
            statusbarField={statusbarField}
            setStatusbarField={setStatusbarField}
            statusbarVisible={statusbarVisible}
            setStatusbarVisible={setStatusbarVisible}
            formCanCreate={formCanCreate}
            formCanEdit={formCanEdit}
            formCanDelete={formCanDelete}
            formCanDuplicate={formCanDuplicate}
            setFormCanCreate={setFormCanCreate}
            setFormCanEdit={setFormCanEdit}
            setFormCanDelete={setFormCanDelete}
            setFormCanDuplicate={setFormCanDuplicate}
            listColumns={listColumns}
            setListColumns={setListColumns}
            listDecorationDanger={listDecorationDanger}
            listDecorationInfo={listDecorationInfo}
            listDecorationMuted={listDecorationMuted}
            setListDecorationDanger={setListDecorationDanger}
            setListDecorationInfo={setListDecorationInfo}
            setListDecorationMuted={setListDecorationMuted}
            listCanCreate={listCanCreate}
            listCanEdit={listCanEdit}
            listCanDelete={listCanDelete}
            listMultiEdit={listMultiEdit}
            listDefaultOrder={listDefaultOrder}
            setListCanCreate={setListCanCreate}
            setListCanEdit={setListCanEdit}
            setListCanDelete={setListCanDelete}
            setListMultiEdit={setListMultiEdit}
            setListDefaultOrder={setListDefaultOrder}
            searchFields={searchFields}
            setSearchFields={setSearchFields}
            searchFilters={searchFilters}
            setSearchFilters={setSearchFilters}
            searchGroupByFilters={searchGroupByFilters}
            setSearchGroupByFilters={setSearchGroupByFilters}
            editingFilterId={editingFilterId}
            setEditingFilterId={setEditingFilterId}
            kanbanFields={kanbanFields}
            setKanbanFields={setKanbanFields}
            kanbanGroupBy={kanbanGroupBy}
            kanbanCanCreate={kanbanCanCreate}
            kanbanQuickCreate={kanbanQuickCreate}
            setKanbanCanCreate={setKanbanCanCreate}
            setKanbanQuickCreate={setKanbanQuickCreate}
            moveKanbanField={moveKanbanField}
            addKanbanField={addKanbanField}
            fields={fields}
            selected={selected}
            setSelected={setSelected}
            addGroup={addGroup}
            addNotebook={addNotebook}
            addButtonToFirstGroup={addButtonToFirstGroup}
            openBindDialog={openBindDialog}
            dropOnGroup={dropOnGroup}
            dropOnPage={dropOnPage}
            removeFormChild={removeFormChild}
            removeNotebookPage={removeNotebookPage}
            renameNotebookPage={renameNotebookPage}
            renameGroup={renameGroup}
            addPageToNotebook={addPageToNotebook}
            removeFormField={removeFormField}
            announceAction={announceAction}
          />


          <DesignerAdvancedMetaAside
            arch={arch}
            snapshots={snapshots}
            busy={busy}
            onRefreshSnapshots={() => void refreshSnapshots()}
            onRollback={(id) => void onRollback(id)}
          />
        </div>
        </Disclosure>
      <DesignerDangerConfirms
        model={model}
        viewType={viewType}
        confirmPhrase={CONFIRM_PHRASE}
        busy={busy}
        confirmOverwriteOpen={confirmOverwriteOpen}
        setConfirmOverwriteOpen={setConfirmOverwriteOpen}
        confirmUnlinkInheritOpen={confirmUnlinkInheritOpen}
        setConfirmUnlinkInheritOpen={setConfirmUnlinkInheritOpen}
        confirmMutateOpen={confirmMutateOpen}
        setConfirmMutateOpen={setConfirmMutateOpen}
        onOverwrite={(phrase) => void onSave({ strategy: "overwrite", confirm_phrase: phrase })}
        onUnlinkInherit={(phrase) => void onUnlinkDesignerInherit(phrase)}
        onMutateParent={(phrase) =>
          void createNewFieldWithInject({
            confirm_advanced: true,
            confirm_phrase: phrase,
          })
        }
      />
        </>
      }
    />
    </DesignerUiProvider>
  );
}
