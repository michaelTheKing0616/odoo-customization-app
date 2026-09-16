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
  getApiBase,
  ConfirmationRequiredError,
  Connection,
  FieldRow,
  GroupRow,
  MailTemplateRow,
  PreviewTheme,
  RelatedPathOption,
  SnapshotRow,
} from "@/lib/api";
import {
  DesignerFieldInspector,
  DesignerFieldInspectorEmpty,
  type DesignerFieldInspectorValues,
} from "@/components/designer/DesignerFieldInspector";
import { XPathInheritPanel, type LocatorIssue } from "@/components/designer/XPathInheritPanel";
import {
  DesignerSessionBar,
  designerPublishState,
} from "@/components/designer/DesignerSessionBar";
import { useDesignerHistory } from "@/components/designer/useDesignerHistory";
import { fallbackWidgetsForTtype, type WidgetOption } from "@/lib/widgetCatalog";
import { automationsHref } from "@/lib/automationForm";
import { useSyncShellContext } from "@/lib/use-sync-shell-context";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Callout } from "@/components/ui/Callout";
import { Card } from "@/components/ui/layout-primitives";
import {
  bindModeSupported,
  bindModeUnsupportedReason,
  connectionSupports,
  connectionUnsupportedReason,
  injectStrategyCapabilityId,
  mutationAllowed,
  mutationBlockedReason,
  gridViewAllowed,
  isEnterpriseEdition,
} from "@/lib/capabilities";
import { odooViewUrl, pickStandaloneWindowAction, sameOriginPreviewUrl } from "@/lib/odoo-urls";

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
  pickTemporalDefaults,
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

  const canvasSnapshot = useMemo<DesignerCanvasSnapshot>(
    () => ({
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
      archOverride,
    }),
    [
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
      archOverride,
    ],
  );

  function applyCanvasSnapshot(snapshot: DesignerCanvasSnapshot) {
    setTitle(snapshot.title);
    setFormChildren(snapshot.formChildren);
    setHeaderButtons(snapshot.headerButtons);
    setButtonBox(snapshot.buttonBox);
    setStatusbarField(snapshot.statusbarField);
    setStatusbarVisible(snapshot.statusbarVisible);
    setFormCanCreate(snapshot.formCanCreate);
    setFormCanEdit(snapshot.formCanEdit);
    setFormCanDelete(snapshot.formCanDelete);
    setFormCanDuplicate(snapshot.formCanDuplicate);
    setListColumns(snapshot.listColumns);
    setListDecorationDanger(snapshot.listDecorationDanger);
    setListDecorationInfo(snapshot.listDecorationInfo);
    setListDecorationMuted(snapshot.listDecorationMuted);
    setListCanCreate(snapshot.listCanCreate);
    setListCanEdit(snapshot.listCanEdit);
    setListCanDelete(snapshot.listCanDelete);
    setListMultiEdit(snapshot.listMultiEdit);
    setListDefaultOrder(snapshot.listDefaultOrder);
    setViewSample(snapshot.viewSample);
    setSearchFields(snapshot.searchFields);
    setSearchFilters(snapshot.searchFilters);
    setSearchGroupByFilters(snapshot.searchGroupByFilters);
    setKanbanFields(snapshot.kanbanFields);
    setKanbanGroupBy(snapshot.kanbanGroupBy);
    setKanbanCanCreate(snapshot.kanbanCanCreate);
    setKanbanQuickCreate(snapshot.kanbanQuickCreate);
    setCalendarDateStart(snapshot.calendarDateStart);
    setCalendarDateStop(snapshot.calendarDateStop);
    setCalendarColor(snapshot.calendarColor);
    setCalendarMode(snapshot.calendarMode);
    setCalendarFields(snapshot.calendarFields);
    setGraphType(snapshot.graphType);
    setGraphFields(snapshot.graphFields);
    setPivotFields(snapshot.pivotFields);
    setMapResPartner(snapshot.mapResPartner);
    setMapRouting(snapshot.mapRouting);
    setMapFields(snapshot.mapFields);
    setActivityFields(snapshot.activityFields);
    setGanttDateStart(snapshot.ganttDateStart);
    setGanttDateStop(snapshot.ganttDateStop);
    setGanttGroupBy(snapshot.ganttGroupBy);
    setGanttColor(snapshot.ganttColor);
    setGanttProgress(snapshot.ganttProgress);
    setGanttDefaultScale(snapshot.ganttDefaultScale);
    setGanttDependencyField(snapshot.ganttDependencyField);
    setGanttFields(snapshot.ganttFields);
    setCohortDateStart(snapshot.cohortDateStart);
    setCohortDateStop(snapshot.cohortDateStop);
    setCohortInterval(snapshot.cohortInterval);
    setCohortMode(snapshot.cohortMode);
    setCohortTimeline(snapshot.cohortTimeline);
    setCohortMeasure(snapshot.cohortMeasure);
    setGridRowField(snapshot.gridRowField);
    setGridColField(snapshot.gridColField);
    setGridMeasure(snapshot.gridMeasure);
    setGridAdjustment(snapshot.gridAdjustment);
    setGridDateStart(snapshot.gridDateStart);
    setGridDateStop(snapshot.gridDateStop);
    setGridFields(snapshot.gridFields);
    setArchOverride(snapshot.archOverride);
  }

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

  const refreshSnapshots = useCallback(async () => {
    try {
      const snaps = await api.listSnapshots(connectionId);
      setSnapshots(snaps.filter((s) => s.resource_type === "view"));
    } catch {
      setSnapshots([]);
    }
  }, [connectionId]);

  useEffect(() => {
    api
      .getConnection(connectionId)
      .then(setConnection)
      .catch((err: Error) => setError(err.message));
    refreshSnapshots().catch(() => undefined);
    api
      .getPreviewTheme(connectionId)
      .then(setPreviewTheme)
      .catch(() => setPreviewTheme(null));
  }, [connectionId, refreshSnapshots]);

  useEffect(() => {
    if (!connectionId) return;
    api
      .listNicheWidgets(connectionId, viewType)
      .then((res) => {
        setNicheWidgets(res.widgets);
        setColorPalette(res.color_palette);
      })
      .catch(() => {
        setNicheWidgets([]);
        setColorPalette([]);
      });
  }, [connectionId, viewType]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const fromQuery = new URLSearchParams(window.location.search).get("model");
    if (fromQuery) setModel(fromQuery);
  }, []);

  useEffect(() => {
    if (!canvasFlashId || typeof document === "undefined") return;
    // Prefer the structural editor (editable drop target), not the Odoo-style preview —
    // both used to share data-canvas-id so scrollIntoView stopped at the preview on top.
    const el =
      document.querySelector(`[data-structure-id="${canvasFlashId}"]`) ??
      document.querySelector(`[data-canvas-id="${canvasFlashId}"]`);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
    const t = window.setTimeout(() => setCanvasFlashId(null), 2200);
    return () => window.clearTimeout(t);
  }, [canvasFlashId]);

  useEffect(() => {
    if (!toolbarFlash) return;
    const t = window.setTimeout(() => setToolbarFlash(null), 1800);
    return () => window.clearTimeout(t);
  }, [toolbarFlash]);

  function announceAction(message: string, flashId?: string | null, toolbarKey?: string) {
    setNotice(message);
    if (flashId) setCanvasFlashId(flashId);
    if (toolbarKey) setToolbarFlash(toolbarKey);
  }

  useEffect(() => {
    if (!connectionId || !model.trim()) {
      setWindowActionId(null);
      return;
    }
    let cancelled = false;
    api
      .listWindowActions(connectionId, { model: model.trim(), standaloneOnly: true })
      .then((rows) => {
        if (cancelled) return;
        setWindowActionId(pickStandaloneWindowAction(rows, viewType));
      })
      .catch(() => {
        if (!cancelled) setWindowActionId(null);
      });
    return () => {
      cancelled = true;
    };
  }, [connectionId, model, viewType]);

  const liveOdooUrl =
    connection?.url && model
      ? odooViewUrl(connection.url, model, viewType, windowActionId)
      : null;
  const proxyPreviewUrl = model
    ? sameOriginPreviewUrl(connectionId, model, viewType, getApiBase())
    : null;

  useEffect(() => {
    setLiveFailed(false);
  }, [proxyPreviewUrl, previewKey, model, viewType]);

  async function loadModelFields(target: string) {
    setError(null);
    setLoadedViewId(null);
    setLastSnapshotId(null);
    try {
      const rows = await api.listFields(connectionId, target);
      setFields(rows);
      setFieldsModel(target);
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
        [], rows,
      );
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

  function moveKanbanField(fieldId: string, dir: -1 | 1) {
    setKanbanFields((cols) => {
      const idx = cols.findIndex((f) => f.id === fieldId);
      if (idx < 0) return cols;
      const next = idx + dir;
      if (next < 0 || next >= cols.length) return cols;
      const copy = [...cols];
      const [item] = copy.splice(idx, 1);
      copy.splice(next, 0, item);
      return copy;
    });
  }

  function findSelectedField(): DesignerField | null {
    if (!selected) return null;
    if (selected.scope === "list") {
      return listColumns.find((f) => f.id === selected.fieldId) ?? null;
    }
    if (selected.scope === "search") {
      return searchFields.find((f) => f.id === selected.fieldId) ?? null;
    }
    if (selected.scope === "kanban") {
      return kanbanFields.find((f) => f.id === selected.fieldId) ?? null;
    }
    if (selected.scope === "form-group") {
      for (const child of formChildren) {
        if (child.kind === "group" && child.id === selected.groupId) {
          const hit = child.children.find((f) => f.id === selected.fieldId);
          return hit && hit.kind === "field" ? hit : null;
        }
      }
      return null;
    }
    for (const child of formChildren) {
      if (child.kind === "notebook" && child.id === selected.notebookId) {
        const page = child.pages.find((p) => p.id === selected.pageId);
        const hit = page?.children.find((f) => f.id === selected.fieldId);
        return hit && hit.kind === "field" ? hit : null;
      }
    }
    return null;
  }

  function removeSelectedField() {
    if (!selected) return;
    const fieldId = selected.fieldId;
    if (selected.scope === "list") {
      setListColumns((cols) => cols.filter((c) => c.id !== fieldId));
    } else if (selected.scope === "search") {
      setSearchFields((cols) => cols.filter((c) => c.id !== fieldId));
    } else if (selected.scope === "kanban") {
      setKanbanFields((cols) => cols.filter((c) => c.id !== fieldId));
    } else if (selected.scope === "form-group") {
      const groupId = selected.groupId;
      setFormChildren((children) =>
        children.map((child) => {
          if (child.kind !== "group" || child.id !== groupId) return child;
          return {
            ...child,
            children: child.children.filter((n) => n.id !== fieldId),
          };
        }),
      );
    } else {
      const { notebookId, pageId } = selected;
      setFormChildren((children) =>
        children.map((child) => {
          if (child.kind !== "notebook" || child.id !== notebookId) return child;
          return {
            ...child,
            pages: child.pages.map((p) =>
              p.id !== pageId
                ? p
                : {
                    ...p,
                    children: p.children.filter((n) => n.id !== fieldId),
                  },
            ),
          };
        }),
      );
    }
    setSelected(null);
  }

  function updateSelectedField(patch: Partial<DesignerFieldInspectorValues>) {
    if (!selected) return;
    pendingCoalesceRef.current = `inspector:${selected.fieldId}`;
    pendingHistoryLabelRef.current = "Edit field properties";
    const { ttype: _ttype, name: _name, ...fieldPatch } = patch;
    if (selected.scope === "list") {
      setListColumns((cols) =>
        cols.map((f) => (f.id === selected.fieldId ? { ...f, ...fieldPatch } : f)),
      );
      return;
    }
    if (selected.scope === "search") {
      setSearchFields((cols) =>
        cols.map((f) => (f.id === selected.fieldId ? { ...f, ...fieldPatch } : f)),
      );
      return;
    }
    if (selected.scope === "kanban") {
      setKanbanFields((cols) =>
        cols.map((f) => (f.id === selected.fieldId ? { ...f, ...fieldPatch } : f)),
      );
      return;
    }
    if (selected.scope === "form-group") {
      setFormChildren((children) =>
        children.map((child) => {
          if (child.kind !== "group" || child.id !== selected.groupId) return child;
          return {
            ...child,
            children: child.children.map((node) => {
              if (node.id !== selected.fieldId || node.kind !== "field") return node;
              return { ...node, ...fieldPatch };
            }),
          };
        }),
      );
      return;
    }
    setFormChildren((children) =>
      children.map((child) => {
        if (child.kind !== "notebook" || child.id !== selected.notebookId) return child;
        return {
          ...child,
          pages: child.pages.map((p) => {
            if (p.id !== selected.pageId) return p;
            return {
              ...p,
              children: p.children.map((node) => {
                if (node.id !== selected.fieldId || node.kind !== "field") return node;
                return { ...node, ...fieldPatch };
              }),
            };
          }),
        };
      }),
    );
  }

  function addGroup() {
    const id = uid("g");
    setFormChildren((c) => [
      ...c,
      { kind: "group", id, string: `Group ${c.length + 1}`, children: [] },
    ]);
    announceAction(`Added group “Group ${formChildren.length + 1}” on the canvas.`, id, "group");
  }

  function addNotebook() {
    const id = uid("n");
    const pageLabel = "Page 1";
    setFormChildren((c) => [
      ...c,
      {
        kind: "notebook",
        id,
        pages: [{ id: uid("p"), string: pageLabel, children: [] }],
      },
    ]);
    announceAction(
      "Added notebook (tab strip) on the canvas below. Prefer “+ Page” on this notebook for another tab — not another notebook.",
      id,
      "notebook",
    );
  }

  function addPageToNotebook(notebookId: string) {
    const pageId = uid("p");
    let pageName = "Page";
    setFormChildren((children) =>
      children.map((child) => {
        if (child.kind !== "notebook" || child.id !== notebookId) return child;
        const n = child.pages.length + 1;
        pageName = `Page ${n}`;
        return {
          ...child,
          pages: [
            ...child.pages,
            { id: pageId, string: pageName, children: [] },
          ],
        };
      }),
    );
    announceAction(`Added tab “${pageName}” to the notebook.`, pageId, "page");
  }

  function removeFormChild(childId: string) {
    const target = formChildren.find((c) => c.id === childId);
    setFormChildren((children) => children.filter((c) => c.id !== childId));
    setSelected((sel) => {
      if (!sel) return null;
      if (sel.scope === "form-group" && sel.groupId === childId) return null;
      if (sel.scope === "form-page" && sel.notebookId === childId) return null;
      return sel;
    });
    announceAction(
      target?.kind === "notebook" ? "Removed notebook from canvas." : "Removed group from canvas.",
      null,
      "remove",
    );
  }

  function removeNotebookPage(notebookId: string, pageId: string) {
    setFormChildren((children) =>
      children
        .map((child) => {
          if (child.kind !== "notebook" || child.id !== notebookId) return child;
          const pages = child.pages.filter((p) => p.id !== pageId);
          if (pages.length === 0) return null;
          return { ...child, pages };
        })
        .filter((c): c is FormChild => c != null),
    );
    setSelected((sel) =>
      sel?.scope === "form-page" && sel.pageId === pageId ? null : sel,
    );
    announceAction("Removed notebook page (tab).", null, "remove");
  }

  function renameNotebookPage(notebookId: string, pageId: string, string: string) {
    setFormChildren((children) =>
      children.map((child) => {
        if (child.kind !== "notebook" || child.id !== notebookId) return child;
        return {
          ...child,
          pages: child.pages.map((p) =>
            p.id === pageId ? { ...p, string: string || p.string } : p,
          ),
        };
      }),
    );
  }

  function renameGroup(groupId: string, string: string) {
    setFormChildren((children) =>
      children.map((child) =>
        child.kind === "group" && child.id === groupId
          ? { ...child, string: string || child.string }
          : child,
      ),
    );
  }

  function openBindDialog(placement: ButtonPlacement, mode: BindDialogMode = "create_update") {
    setBindPlacement(placement);
    setBindMode(mode);
    setError(null);
    if (mode === "bind_existing" && model) {
      void api
        .listBindableActions(connectionId, model)
        .then((rows) => {
          setBindableActions(rows);
          setSelectedActionId(rows[0]?.id ?? "");
        })
        .catch((err) => setError(err instanceof Error ? err.message : "Failed to list actions"));
    }
    if (mode === "create_activity") {
      void api
        .listActivityTypes(connectionId)
        .then((rows) => {
          setActivityTypes(rows);
          setBindActivityTypeId(rows[0]?.id ?? "");
        })
        .catch((err) => setError(err instanceof Error ? err.message : "Failed to list activity types"));
    }
    if (mode === "create_mail" && model) {
      void api
        .listMailTemplates(connectionId, model)
        .then((rows) => {
          setMailTemplates(rows);
          setBindMailTemplateId(rows[0]?.id ?? "");
        })
        .catch(() => setMailTemplates([]));
    }
  }

  function placeBoundButton(btn: DesignerButton) {
    if (bindPlacement === "header") {
      setHeaderButtons((all) => [...all, btn]);
    } else if (bindPlacement === "button_box") {
      setButtonBox((all) => [
        ...all,
        {
          ...btn,
          class_name: btn.class_name || "oe_stat_button",
          icon: btn.icon || bindIcon || "fa-list",
        },
      ]);
    } else {
      setFormChildren((children) => {
        if (!children.length) {
          return [{ kind: "group", id: uid("g"), string: "Main", children: [btn] }];
        }
        return children.map((child, idx) => {
          if (idx !== 0 || child.kind !== "group") return child;
          return { ...child, children: [...child.children, btn] };
        });
      });
    }
  }

  async function submitBindDialog(opts?: {
    confirm_advanced?: boolean;
    confirm_phrase?: string;
  }) {
    if (!model) {
      setError("Enter a model first");
      return;
    }
    if (bindMode !== "closed" && !bindModeSupported(connection, bindMode)) {
      setError(
        bindModeUnsupportedReason(connection, bindMode) ??
          "Bind mode unavailable on this Odoo version",
      );
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (bindMode === "create_update") {
        const created = await api.createUpdateFieldAction(connectionId, {
          name: bindLabel,
          model,
          field_name: bindFieldName,
          value: bindValue,
          bind_to_model: true,
        });
        placeBoundButton({
          kind: "button",
          id: uid("b"),
          string: bindLabel,
          name: String(created.id),
          type: "action",
          class_name: bindPlacement === "header" ? "btn-primary" : undefined,
        });
        setNotice(`Created server action #${created.id} and bound button (${bindPlacement}). Save the view to apply.`);
      } else if (bindMode === "create_related") {
        const created = await api.createRelatedWindowAction(connectionId, {
          name: bindLabel,
          source_model: model,
          target_model: bindTargetModel,
          relation_field: bindRelationField,
        });
        placeBoundButton({
          kind: "button",
          id: uid("b"),
          string: bindLabel,
          name: String(created.id),
          type: "action",
          class_name: bindPlacement === "button_box" ? "oe_stat_button" : "btn-secondary",
          icon: bindPlacement === "button_box" ? bindIcon : undefined,
        });
        setNotice(`Created window action #${created.id} and bound button (${bindPlacement}). Save the view to apply.`);
      } else if (bindMode === "create_activity") {
        if (bindActivityTypeId === "") {
          setError("Pick an activity type");
          return;
        }
        const created = await api.createNextActivityAction(connectionId, {
          name: bindLabel,
          model,
          activity_type_id: bindActivityTypeId,
          summary: bindActivitySummary || "Follow up",
          note: bindActivityNote || null,
          user_type: "generic",
          user_field_name: undefined,
          bind_to_model: true,
        });
        placeBoundButton({
          kind: "button",
          id: uid("b"),
          string: bindLabel,
          name: String(created.id),
          type: "action",
          class_name: bindPlacement === "header" ? "btn-primary" : undefined,
        });
        setNotice(`Created next-activity action #${created.id} (${bindPlacement}). Save the view to apply.`);
      } else if (bindMode === "create_mail") {
        const created = await api.createMailPostAction(connectionId, {
          name: bindLabel,
          model,
          template_id: bindMailTemplateId === "" ? null : bindMailTemplateId,
          mail_post_method: bindMailMethod,
          subject: bindMailSubject || null,
          body_html: bindMailBody || null,
          email_to: bindMailEmailTo || null,
          bind_to_model: true,
        });
        placeBoundButton({
          kind: "button",
          id: uid("b"),
          string: bindLabel,
          name: String(created.id),
          type: "action",
          class_name: bindPlacement === "header" ? "btn-primary" : undefined,
        });
        setNotice(`Created mail-post action #${created.id} (${bindPlacement}). Save the view to apply.`);
      } else if (bindMode === "create_smart") {
        if (bindCreateCountField) {
          const phrase = (opts?.confirm_phrase || bindSmartConfirmPhrase).trim();
          if (phrase !== CONFIRM_PHRASE) {
            setError(`Create count field requires confirm phrase: ${CONFIRM_PHRASE}`);
            return;
          }
          if (!bindOne2manyField.trim()) {
            setError("one2many field on source model is required for count field");
            return;
          }
        }
        const bundle = await api.createSmartButtonBundle(connectionId, {
          name: bindLabel,
          source_model: model,
          target_model: bindTargetModel,
          relation_field: bindRelationField,
          one2many_field: bindOne2manyField.trim() || null,
          count_field_name: bindCountFieldName.trim() || null,
          create_count_field: bindCreateCountField,
          icon: bindIcon || "fa-list",
          confirm_advanced: bindCreateCountField
            ? opts?.confirm_advanced ?? true
            : false,
          confirm_phrase: bindCreateCountField
            ? opts?.confirm_phrase || bindSmartConfirmPhrase || CONFIRM_PHRASE
            : null,
        });
        const spec = bundle.button_spec;
        placeBoundButton({
          kind: "button",
          id: uid("b"),
          string: String(spec.string || bindLabel),
          name: String(spec.name || bundle.window_action.id),
          type: "action",
          class_name: String(spec.class || "oe_stat_button"),
          icon: String(spec.icon || bindIcon || "fa-list"),
          count_field: bundle.count_field || undefined,
        });
        setNotice(
          `Smart button bundle: window #${bundle.window_action.id}` +
            (bundle.count_field ? ` · count ${bundle.count_field}` : "") +
            `. Save the view to apply.`,
        );
      } else if (bindMode === "bind_existing") {
        if (selectedActionId === "") {
          setError("Pick an existing action");
          return;
        }
        placeBoundButton({
          kind: "button",
          id: uid("b"),
          string: bindLabel,
          name: String(selectedActionId),
          type: "action",
          class_name:
            bindPlacement === "button_box"
              ? "oe_stat_button"
              : bindPlacement === "header"
                ? "btn-primary"
                : undefined,
          icon: bindPlacement === "button_box" ? bindIcon : undefined,
        });
        setNotice(`Bound button to action #${selectedActionId}. Save the view to apply.`);
      }
      setBindMode("closed");
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setError(`${err.warning} Type “${err.confirm_phrase}” and retry.`);
        setBindSmartConfirmPhrase(err.confirm_phrase || CONFIRM_PHRASE);
      } else {
        setError(err instanceof Error ? err.message : "Failed to bind action");
      }
    } finally {
      setBusy(false);
    }
  }

  function addButtonToFirstGroup() {
    openBindDialog("inline", "create_update");
  }

  function resolveDragFieldName(e?: DragEvent | null): string | null {
    const fromTransfer = e?.dataTransfer?.getData("text/odoo-field")?.trim();
    if (fromTransfer) return fromTransfer;
    return dragField;
  }

  function addFieldToGroup(groupId: string, fieldName: string, index?: number) {
    const meta = fields.find((f) => f.name === fieldName);
    const node: DesignerField = {
      kind: "field",
      id: uid("f"),
      name: fieldName,
      string: meta?.field_description,
    };
    setFormChildren((children) =>
      children.map((child) => {
        if (child.kind === "group" && child.id === groupId) {
          if (child.children.some((n) => n.kind === "field" && n.name === fieldName)) {
            return child;
          }
          const next =
            index == null ? [...child.children, node] : insertAt(child.children, index, node);
          return { ...child, children: next };
        }
        return child;
      }),
    );
    announceAction(
      `Added ${meta?.field_description || fieldName} to group.`,
      groupId,
      "drop",
    );
  }

  function dropOnGroup(groupId: string, e?: DragEvent | null, index?: number) {
    const fieldName = resolveDragFieldName(e);
    if (!fieldName) return;
    addFieldToGroup(groupId, fieldName, index);
    setDragField(null);
  }

  function dropOnPage(notebookId: string, pageId: string, e?: DragEvent | null) {
    const fieldName = resolveDragFieldName(e);
    if (!fieldName) return;
    dropFieldOnPage(notebookId, pageId, fieldName);
    setDragField(null);
  }

  function dropFieldOnPage(
    notebookId: string,
    pageId: string,
    fieldName: string,
    index?: number,
  ) {
    const meta = fields.find((f) => f.name === fieldName);
    const node: DesignerField = {
      kind: "field",
      id: uid("f"),
      name: fieldName,
      string: meta?.field_description,
    };
    setFormChildren((children) =>
      children.map((child) => {
        if (child.kind !== "notebook" || child.id !== notebookId) return child;
        return {
          ...child,
          pages: child.pages.map((p) => {
            if (p.id !== pageId) return p;
            if (p.children.some((n) => n.kind === "field" && n.name === fieldName)) {
              return p;
            }
            const next = index == null ? [...p.children, node] : insertAt(p.children, index, node);
            return { ...p, children: next };
          }),
        };
      }),
    );
    announceAction(
      `Added ${meta?.field_description || fieldName} to notebook tab.`,
      pageId,
      "drop",
    );
  }

  function reorderFormNode(
    fieldId: string,
    dest:
      | { kind: "group"; groupId: string }
      | { kind: "page"; notebookId: string; pageId: string },
    index: number,
  ) {
    setFormChildren((children) => {
      let moved: DesignerField | DesignerButton | null = null;
      const stripped = children.map((child) => {
        if (child.kind === "group") {
          const found = child.children.find((n) => n.id === fieldId);
          if (found) moved = found;
          return { ...child, children: child.children.filter((n) => n.id !== fieldId) };
        }
        return {
          ...child,
          pages: child.pages.map((p) => {
            const found = p.children.find((n) => n.id === fieldId);
            if (found) moved = found;
            return { ...p, children: p.children.filter((n) => n.id !== fieldId) };
          }),
        };
      });
      if (!moved) return children;
      return stripped.map((child) => {
        if (dest.kind === "group" && child.kind === "group" && child.id === dest.groupId) {
          return { ...child, children: insertAt(child.children, index, moved!) };
        }
        if (
          dest.kind === "page" &&
          child.kind === "notebook" &&
          child.id === dest.notebookId
        ) {
          return {
            ...child,
            pages: child.pages.map((p) =>
              p.id === dest.pageId
                ? { ...p, children: insertAt(p.children, index, moved!) }
                : p,
            ),
          };
        }
        return child;
      });
    });
  }

  function selectCanvasField(fieldId: string) {
    for (const child of formChildren) {
      if (child.kind === "group") {
        if (child.children.some((n) => n.kind === "field" && n.id === fieldId)) {
          setSelected({ scope: "form-group", groupId: child.id, fieldId });
          setRailTab("properties");
          return;
        }
      } else {
        for (const page of child.pages) {
          if (page.children.some((n) => n.kind === "field" && n.id === fieldId)) {
            setSelected({
              scope: "form-page",
              notebookId: child.id,
              pageId: page.id,
              fieldId,
            });
            setRailTab("properties");
            return;
          }
        }
      }
    }
  }

  function addListColumn(fieldName: string) {
    if (listColumns.some((c) => c.name === fieldName)) return;
    const meta = fields.find((f) => f.name === fieldName);
    setListColumns((cols) => [
      ...cols,
      {
        kind: "field",
        id: uid("f"),
        name: fieldName,
        string: meta?.field_description,
      },
    ]);
  }

  function addSearchField(fieldName: string) {
    if (searchFields.some((c) => c.name === fieldName)) return;
    const meta = fields.find((f) => f.name === fieldName);
    setSearchFields((cols) => [
      ...cols,
      {
        kind: "field",
        id: uid("f"),
        name: fieldName,
        string: meta?.field_description,
      },
    ]);
  }

  function addKanbanField(fieldName: string) {
    if (kanbanFields.some((c) => c.name === fieldName)) return;
    const meta = fields.find((f) => f.name === fieldName);
    setKanbanFields((cols) => [
      ...cols,
      {
        kind: "field",
        id: uid("f"),
        name: fieldName,
        string: meta?.field_description,
      },
    ]);
  }

  async function addNicheWidget(entry: NicheWidgetEntry) {
    if (!model) {
      setError("Select a model first");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      let fieldName: string | undefined;
      const support = entry.supporting_field;
      let fieldRows = fields;

      const existing = fields.find(
        (f) =>
          entry.recommended_ttypes.includes(f.ttype) &&
          (!support || f.name === support.name),
      );
      if (existing) {
        fieldName = existing.name;
      } else if (support) {
        if (!fields.some((f) => f.name === support.name)) {
          await api.createField(connectionId, {
            model,
            name: support.name,
            field_description: support.string || support.name,
            ttype: support.ttype,
            inject_into_views: false,
            inject_strategy: "inherit",
            confirm_advanced: true,
            confirm_phrase: CONFIRM_PHRASE,
            ...(support.relation ? { relation: support.relation } : {}),
            ...(support.ttype === "selection"
              ? {
                  selection: [
                    { value: "normal", label: "Normal" },
                    { value: "done", label: "Done" },
                    { value: "blocked", label: "Blocked" },
                  ],
                }
              : {}),
          });
          fieldRows = await api.listFields(connectionId, model);
          setFields(fieldRows);
          setFieldsModel(model);
        }
        fieldName = support.name;
      } else {
        const match = fields.find((f) => entry.recommended_ttypes.includes(f.ttype));
        if (!match) {
          setNotice(
            `Add a ${entry.recommended_ttypes.join("/")} field first for ${entry.label}`,
          );
          return;
        }
        fieldName = match.name;
      }

      const meta = fieldRows.find((f) => f.name === fieldName);
      const node: DesignerField = {
        kind: "field",
        id: uid("f"),
        name: fieldName,
        string: meta?.field_description,
        widget: entry.id,
      };

      if (viewType === "kanban") {
        if (kanbanFields.some((c) => c.name === fieldName && c.widget === entry.id)) return;
        setKanbanFields((cols) => [...cols, node]);
        setSelected({ scope: "kanban", fieldId: node.id });
      } else if (viewType === "list") {
        if (listColumns.some((c) => c.name === fieldName && c.widget === entry.id)) return;
        setListColumns((cols) => [...cols, node]);
        setSelected({ scope: "list", fieldId: node.id });
      } else if (viewType === "form") {
        const firstGroup = formChildren.find((c) => c.kind === "group");
        if (!firstGroup) {
          setNotice("Add a form group before niche widgets");
          return;
        }
        setFormChildren((children) =>
          children.map((child) =>
            child.kind === "group" && child.id === firstGroup.id
              ? { ...child, children: [...child.children, node] }
              : child,
          ),
        );
        setSelected({ scope: "form-group", groupId: firstGroup.id, fieldId: node.id });
      } else {
        setNotice(`${entry.label} is available on form, list, and kanban views`);
        return;
      }
      announceAction(`Added ${entry.label} (${entry.id})`, node.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add niche widget");
    } finally {
      setBusy(false);
    }
  }

  function removeFormField(
    container: "group" | "page",
    containerId: string,
    fieldId: string,
    notebookId?: string,
  ) {
    setFormChildren((children) =>
      children.map((child) => {
        if (container === "group" && child.kind === "group" && child.id === containerId) {
          return { ...child, children: child.children.filter((f) => f.id !== fieldId) };
        }
        if (
          container === "page" &&
          child.kind === "notebook" &&
          child.id === notebookId
        ) {
          return {
            ...child,
            pages: child.pages.map((p) =>
              p.id === containerId
                ? { ...p, children: p.children.filter((f) => f.id !== fieldId) }
                : p,
            ),
          };
        }
        return child;
      }),
    );
    setSelected((sel) => (sel?.fieldId === fieldId ? null : sel));
  }

  async function createNewFieldWithInject(opts?: {
    confirm_advanced?: boolean;
    confirm_phrase?: string;
  }) {
    if (!model || !newFieldName.startsWith("x_")) return;
    const strategyCap = injectStrategyCapabilityId(injectStrategy);
    if (!connectionSupports(connection, strategyCap)) {
      setError(
        connectionUnsupportedReason(connection, strategyCap) ??
          "Inject strategy unavailable on this Odoo version",
      );
      return;
    }
    if (injectStrategy === "mutate" && !opts?.confirm_advanced) {
      setConfirmMutateOpen(true);
      return;
    }
    setBusy(true);
    setError(null);
    const createdName = newFieldName;
    try {
      await api.createField(connectionId, {
        model,
        name: createdName,
        field_description: newFieldLabel || createdName,
        ttype: newFieldType,
        inject_into_views: true,
        inject_strategy: injectStrategy,
        ...(injectStrategy === "mutate"
          ? {
              confirm_advanced: true,
              confirm_phrase:
                opts?.confirm_phrase || confirmPhrase || CONFIRM_PHRASE,
            }
          : {
              confirm_advanced: true,
              confirm_phrase: confirmPhrase || CONFIRM_PHRASE,
            }),
        ...(newFieldType === "many2one" ? { relation: "res.partner" } : {}),
        ...(newFieldType === "selection"
          ? {
              selection: [
                { value: "a", label: "A" },
                { value: "b", label: "B" },
              ],
            }
          : {}),
      });
      setNewFieldName("");
      setConfirmMutateOpen(false);
      // Soft refresh: keep loaded Form layout; do not call loadModelFields (that reseeds/wipes).
      const rows = await refreshModelFieldsOnly(model);
      appendFieldToCurrentLayout(createdName, rows);
      setNotice(
        `Created ${createdName}` +
          (injectStrategy === "mutate" ? " (mutate inject)" : " (inherit inject)") +
          ". Field list and layout kept — no need to reload the view.",
      );
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmMutateOpen(true);
        setError(`${err.warning} Type “${err.confirm_phrase}” and retry.`);
        setConfirmPhrase(err.confirm_phrase || CONFIRM_PHRASE);
      } else {
        setError(err instanceof Error ? err.message : "Create field failed");
      }
    } finally {
      setBusy(false);
    }
  }

  async function onSave(opts?: {
    arch?: string;
    strategy?: "inherit" | "overwrite";
    confirm_phrase?: string;
  }) {
    if (!model) {
      setError("Load a model first");
      return;
    }
    const strategy = opts?.strategy ?? saveStrategy;
    // Stock models default to inherit — overwrite only via confirmed Power path
    if (!model.startsWith("x_") && strategy === "overwrite" && !opts?.confirm_phrase) {
      setConfirmOverwriteOpen(true);
      return;
    }
    if (strategy === "overwrite" && !opts?.confirm_phrase && model.startsWith("x_")) {
      setConfirmOverwriteOpen(true);
      return;
    }
    const useArch = opts?.arch ?? archOverride;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const saved = await api.saveView(connectionId, {
        model,
        view_type: viewType,
        name:
          strategy === "inherit"
            ? `${model}.designer.${viewType}`
            : `${model}.${viewType}`,
        view_id: strategy === "overwrite" ? (loadedViewId ?? undefined) : undefined,
        ...(useArch ? { arch: useArch } : { spec: activeViewSpec }),
        create_if_missing: true,
        strategy,
        ...(strategy === "overwrite"
          ? {
              confirm_advanced: true,
              confirm_phrase: opts?.confirm_phrase || CONFIRM_PHRASE,
            }
          : {}),
      });
      setLoadedViewId(saved.id);
      setConfirmOverwriteOpen(false);
      if (saved.snapshot_id) {
        setLastSnapshotId(saved.snapshot_id);
        setNotice(
          `Published ${viewType} view #${saved.id}. Checkpoint ${saved.snapshot_id.slice(0, 8)}… is in published history.`,
        );
      } else {
        setNotice(`Saved new ${viewType} view #${saved.id} for ${model}`);
      }
      setArch(saved.arch ?? arch);
      setArchOverride(null);
      setPreviewKey((k) => k + 1);
      if (archOverride !== null) {
        historySkipRef.current = "apply";
      }
      history.reset({ ...canvasSnapshot, archOverride: null });
      await refreshSnapshots();
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmOverwriteOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Save failed");
      }
    } finally {
      setBusy(false);
    }
  }

  async function onRepairDuplicateChrome() {
    if (!model) {
      setError("Load a model first");
      return;
    }
    if (model.startsWith("x_") || viewType !== "form") {
      setError("Fix duplicate chrome applies to stock form views (e.g. account.move).");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const out = await api.repairDesignerInherit(connectionId, {
        model,
        view_type: "form",
      });
      if (out.snapshot_id) setLastSnapshotId(out.snapshot_id);
      setNotice(out.detail || `Repair: ${out.action}`);
      await refreshSnapshots();
      await loadExistingView();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Repair failed");
    } finally {
      setBusy(false);
    }
  }

  async function onUnlinkDesignerInherit(phrase: string) {
    if (!model) {
      setError("Load a model first");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const out = await api.unlinkDesignerInherit(connectionId, {
        model,
        view_type: viewType,
        confirm_advanced: true,
        confirm_phrase: phrase,
      });
      setConfirmUnlinkInheritOpen(false);
      if (out.snapshot_id) setLastSnapshotId(out.snapshot_id);
      setNotice(out.detail || `Unlink: ${out.action}`);
      await refreshSnapshots();
      await loadExistingView();
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmUnlinkInheritOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Unlink failed");
      }
    } finally {
      setBusy(false);
    }
  }

  async function runXpathPreview() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.xpathPreview(connectionId, {
        expr: xpathExpr,
        position: xpathPosition,
        body_xml: xpathBody,
        parent_arch: arch || null,
        view_type: viewType,
      });
      setXpathArchPreview(res.arch);
      const located = res.locator_issues ?? [];
      setXpathIssues(located);
      setXpathSuggested(res.suggested_expr ?? null);
      setXpathDefaultInject(res.default_inject_expr ?? null);
      setXpathMatchCount(res.match_count ?? null);
      setXpathBlocking(Boolean(res.blocking));
      if (res.blocking) {
        setNotice("XPath preview found a blocking locator issue.");
      } else if (located.some((i) => i.severity === "warning") || (res.issues?.length ?? 0) > 0) {
        setNotice("XPath preview built with upgrade-safety warnings.");
      } else {
        setNotice("XPath preview OK — named locator matches the parent view.");
      }
      return res;
    } catch (err) {
      setError(err instanceof Error ? err.message : "XPath preview failed");
      setXpathArchPreview("");
      setXpathIssues([]);
      setXpathBlocking(false);
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function onSaveXpathInherit() {
    const res = await runXpathPreview();
    if (!res || res.blocking) {
      return;
    }
    await onSave({ arch: res.arch, strategy: "inherit" });
  }

  function onSessionUndo() {
    const snapshot = history.undo();
    if (!snapshot) {
      setNotice(
        lastSnapshotId
          ? "Nothing to undo in this session. Use roll back last publish to restore a snapshot."
          : "Nothing to undo in this session. Save to Odoo first creates a published checkpoint.",
      );
      return;
    }
    historySkipRef.current = "apply";
    applyCanvasSnapshot(snapshot);
    setNotice("Reverted the last unpublished canvas edit.");
  }

  function onSessionRedo() {
    const snapshot = history.redo();
    if (!snapshot) return;
    historySkipRef.current = "apply";
    applyCanvasSnapshot(snapshot);
    setNotice("Restored the unpublished canvas edit.");
  }

  async function onRollbackLastPublish() {
    if (!lastSnapshotId) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.rollbackSnapshot(connectionId, lastSnapshotId);
      setNotice(`Rolled back to snapshot — restored view #${res.id}`);
      setLastSnapshotId(null);
      await loadExistingView();
      await refreshSnapshots();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rollback failed");
    } finally {
      setBusy(false);
    }
  }

  async function onRollback(snapshotId: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await api.rollbackSnapshot(connectionId, snapshotId);
      setNotice(`Restored ${res.restored} #${res.id}`);
      if (snapshotId === lastSnapshotId) setLastSnapshotId(null);
      await loadExistingView();
      await refreshSnapshots();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rollback failed");
    } finally {
      setBusy(false);
    }
  }

  const selectedField = findSelectedField();

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
        <Card className="flex flex-wrap items-end gap-3 p-3" data-testid="designer-studio-toolbar">
          <label className="text-sm">
            <span className="text-muted">Model</span>
            <input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              onBlur={() => {
                if (model.trim()) void ensureFieldsForModel(model);
              }}
              className="mt-1 block w-64 border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
              placeholder="x_ticket"
            />
          </label>
          <button
            type="button"
            onClick={() => model && loadModelFields(model)}
            className="h-10 border border-border-subtle px-4 text-sm text-muted"
          >
            Load fields
          </button>
          <button
            type="button"
            disabled={busy || !model}
            onClick={loadExistingView}
            className="h-10 border border-border-subtle px-4 text-sm text-muted disabled:opacity-60"
          >
            Load existing view
          </button>
          <label className="text-sm">
            <span className="text-muted">View type</span>
            <select
              value={viewType}
              onChange={(e) => {
                const next = e.target.value as ViewType;
                setViewType(next);
                setSelected(null);
                if (
                  model.trim() &&
                  (next === "calendar" ||
                    next === "gantt" ||
                    next === "cohort" ||
                    next === "grid" ||
                    next === "activity" ||
                    next === "map")
                ) {
                  void ensureFieldsForModel(model);
                }
              }}
              className="mt-1 block border border-border-subtle bg-surface px-3 py-2"
            >
              <option value="form">form</option>
              <option value="list">
                list
                {!connectionSupports(connection, "list_as_list_type")
                  ? " (stored as tree on this Odoo)"
                  : ""}
              </option>
              <option value="search">search</option>
              <option value="kanban">kanban</option>
              <option value="calendar" disabled={!mutationAllowed(connection)}>
                calendar
                {!mutationAllowed(connection) ? " (probe connection)" : ""}
              </option>
              <option value="graph" disabled={!mutationAllowed(connection)}>
                graph
                {!mutationAllowed(connection) ? " (probe connection)" : ""}
              </option>
              <option value="pivot" disabled={!mutationAllowed(connection)}>
                pivot
                {!mutationAllowed(connection) ? " (probe connection)" : ""}
              </option>
              <option value="map" disabled={!mutationAllowed(connection)}>
                map
                {!mutationAllowed(connection) ? " (probe connection)" : ""}
              </option>
              <option value="activity" disabled={!mutationAllowed(connection)}>
                activity
                {!mutationAllowed(connection) ? " (probe connection)" : ""}
              </option>
              <option value="gantt" disabled={!mutationAllowed(connection)}>
                gantt
                {!mutationAllowed(connection) ? " (probe connection)" : ""}
              </option>
              <option value="cohort" disabled={!mutationAllowed(connection)}>
                cohort
                {!mutationAllowed(connection) ? " (probe connection)" : ""}
              </option>
              <option value="grid" disabled={!gridViewAllowed(connection)}>
                grid
                {!gridViewAllowed(connection)
                  ? !isEnterpriseEdition(connection?.capabilities)
                    ? " (Enterprise edition)"
                    : " (probe connection)"
                  : ""}
              </option>
            </select>
            {!mutationAllowed(connection) && (
              <p className="mt-1 text-xs text-warning">
                {mutationBlockedReason(connection) ??
                  "Reporting views need a probed connection."}
              </p>
            )}
          </label>
          {viewType === "kanban" && (
            <label className="text-sm">
              <span className="text-muted">Column field</span>
              <select
                value={kanbanGroupBy}
                onChange={(e) => setKanbanGroupBy(e.target.value)}
                className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
              >
                <option value="">(none)</option>
                {fields.map((f) => (
                  <option key={f.id} value={f.name}>
                    {f.name} · {f.ttype}
                  </option>
                ))}
              </select>
            </label>
          )}
          {(viewType === "calendar" ||
            viewType === "graph" ||
            viewType === "pivot" ||
            viewType === "map" ||
            viewType === "activity" ||
            viewType === "gantt" ||
            viewType === "cohort" ||
            viewType === "grid") && (
            <details
              className="w-full rounded-md border border-border-subtle bg-surface px-3 py-2"
              data-testid="designer-view-axes"
              open
            >
              <summary className="cursor-pointer text-sm font-medium text-ink">
                View axes
              </summary>
              <div className="mt-2 flex flex-wrap items-end gap-3">
          {viewType === "calendar" && (
            <>
              <label className="text-sm">
                <span className="text-muted">date_start</span>
                <select
                  value={calendarDateStart}
                  onChange={(e) => setCalendarDateStart(e.target.value)}
                  className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                >
                  <option value="">(required)</option>
                  {dateFieldsForSelect.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name} · {f.ttype}
                      {f.field_description ? ` — ${f.field_description}` : ""}
                    </option>
                  ))}
                </select>
                {fieldsModel && fieldsModel !== model.trim() && (
                  <p className="mt-1 text-xs text-warning">
                    Fields loaded for {fieldsModel || "(none)"} — click Load fields for{" "}
                    {model || "this model"}.
                  </p>
                )}
                {!dateFieldsForSelect.length && (
                  <p className="mt-1 text-xs text-warning">
                    No date/datetime fields on loaded model. Set model to x_lib_loan and click
                    Load fields.
                  </p>
                )}
              </label>
              <label className="text-sm">
                <span className="text-muted">date_stop</span>
                <select
                  value={calendarDateStop}
                  onChange={(e) => setCalendarDateStop(e.target.value)}
                  className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                >
                  <option value="">(optional)</option>
                  {dateFieldsForSelect.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name} · {f.ttype}
                      {f.field_description ? ` — ${f.field_description}` : ""}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="text-muted">color</span>
                <select
                  value={calendarColor}
                  onChange={(e) => setCalendarColor(e.target.value)}
                  className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                >
                  <option value="">(optional)</option>
                  {fields.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="text-muted">mode</span>
                <select
                  value={calendarMode}
                  onChange={(e) => setCalendarMode(e.target.value)}
                  className="mt-1 block border border-border-subtle bg-surface px-3 py-2 text-sm"
                >
                  <option value="">(default)</option>
                  <option value="day">day</option>
                  <option value="week">week</option>
                  <option value="month">month</option>
                </select>
              </label>
            </>
          )}
          {viewType === "graph" && (
            <>
            <label className="text-sm">
              <span className="text-muted">Graph type</span>
              <select
                value={graphType}
                onChange={(e) =>
                  setGraphType(e.target.value as "bar" | "line" | "pie")
                }
                className="mt-1 block border border-border-subtle bg-surface px-3 py-2 text-sm"
              >
                <option value="bar">bar</option>
                <option value="line">line</option>
                <option value="pie">pie</option>
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={viewSample}
                onChange={(e) => setViewSample(e.target.checked)}
                data-testid="designer-view-sample"
              />
              sample data
            </label>
            </>
          )}
          {viewType === "pivot" && (
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={viewSample}
                onChange={(e) => setViewSample(e.target.checked)}
                data-testid="designer-view-sample"
              />
              sample data
            </label>
          )}
          {viewType === "map" && (
            <>
            <label className="text-sm">
              <span className="text-muted">res_partner</span>
              <select
                value={mapResPartner}
                onChange={(e) => setMapResPartner(e.target.value)}
                className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                data-testid="designer-map-res-partner"
              >
                <option value="">(required — partner m2o)</option>
                {fields
                  .filter((f) => f.ttype === "many2one")
                  .map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name}
                      {f.relation ? ` · ${f.relation}` : " · many2one"}
                      {f.relation === "res.partner" ? " ✓" : ""}
                    </option>
                  ))}
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={mapRouting}
                onChange={(e) => setMapRouting(e.target.checked)}
                data-testid="designer-map-routing"
              />
              routing (directions)
            </label>
            </>
          )}
          {viewType === "gantt" && (
            <>
              <label className="text-sm">
                <span className="text-muted">date_start</span>
                <select
                  value={ganttDateStart}
                  onChange={(e) => setGanttDateStart(e.target.value)}
                  className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                >
                  <option value="">(required)</option>
                  {dateFieldsForSelect.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name} · {f.ttype}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="text-muted">date_stop</span>
                <select
                  value={ganttDateStop}
                  onChange={(e) => setGanttDateStop(e.target.value)}
                  className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                >
                  <option value="">(optional)</option>
                  {dateFieldsForSelect.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="text-muted">default_group_by</span>
                <select
                  value={ganttGroupBy}
                  onChange={(e) => setGanttGroupBy(e.target.value)}
                  className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                >
                  <option value="">(optional)</option>
                  {fields.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="text-muted">color</span>
                <select
                  value={ganttColor}
                  onChange={(e) => setGanttColor(e.target.value)}
                  className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                >
                  <option value="">(optional)</option>
                  {fields.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="text-muted">progress</span>
                <select
                  value={ganttProgress}
                  onChange={(e) => setGanttProgress(e.target.value)}
                  className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                  data-testid="designer-gantt-progress"
                >
                  <option value="">(optional)</option>
                  {fields.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name} · {f.ttype}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="text-muted">default_scale</span>
                <select
                  value={ganttDefaultScale}
                  onChange={(e) => setGanttDefaultScale(e.target.value)}
                  className="mt-1 block border border-border-subtle bg-surface px-3 py-2 text-sm"
                  data-testid="designer-gantt-default-scale"
                >
                  <option value="">(optional)</option>
                  <option value="day">day</option>
                  <option value="week">week</option>
                  <option value="month">month</option>
                  <option value="year">year</option>
                </select>
              </label>
              <label className="text-sm">
                <span className="text-muted">dependency_field</span>
                <select
                  value={ganttDependencyField}
                  onChange={(e) => setGanttDependencyField(e.target.value)}
                  className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                  data-testid="designer-gantt-dependency"
                >
                  <option value="">(optional)</option>
                  {fields
                    .filter((f) => f.ttype === "many2many" || f.ttype === "one2many")
                    .map((f) => (
                      <option key={f.id} value={f.name}>
                        {f.name} · {f.ttype}
                      </option>
                    ))}
                </select>
              </label>
            </>
          )}
          {viewType === "cohort" && (
            <>
              <label className="text-sm">
                <span className="text-muted">date_start</span>
                <select
                  value={cohortDateStart}
                  onChange={(e) => setCohortDateStart(e.target.value)}
                  className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                >
                  <option value="">(required)</option>
                  {dateFieldsForSelect.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name} · {f.ttype}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="text-muted">date_stop</span>
                <select
                  value={cohortDateStop}
                  onChange={(e) => setCohortDateStop(e.target.value)}
                  className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                >
                  <option value="">(optional)</option>
                  {dateFieldsForSelect.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="text-muted">interval</span>
                <select
                  value={cohortInterval}
                  onChange={(e) =>
                    setCohortInterval(
                      e.target.value as "day" | "week" | "month" | "year" | "",
                    )
                  }
                  className="mt-1 block border border-border-subtle bg-surface px-3 py-2 text-sm"
                >
                  <option value="day">day</option>
                  <option value="week">week</option>
                  <option value="month">month</option>
                  <option value="year">year</option>
                </select>
              </label>
              <label className="text-sm">
                <span className="text-muted">mode</span>
                <select
                  value={cohortMode}
                  onChange={(e) =>
                    setCohortMode(e.target.value as "retention" | "churn" | "")
                  }
                  className="mt-1 block border border-border-subtle bg-surface px-3 py-2 text-sm"
                  data-testid="designer-cohort-mode"
                >
                  <option value="retention">retention</option>
                  <option value="churn">churn</option>
                </select>
              </label>
              <label className="text-sm">
                <span className="text-muted">timeline</span>
                <select
                  value={cohortTimeline}
                  onChange={(e) =>
                    setCohortTimeline(e.target.value as "forward" | "backward" | "")
                  }
                  className="mt-1 block border border-border-subtle bg-surface px-3 py-2 text-sm"
                >
                  <option value="">(default)</option>
                  <option value="forward">forward</option>
                  <option value="backward">backward</option>
                </select>
              </label>
              <label className="text-sm">
                <span className="text-muted">measure</span>
                <select
                  value={cohortMeasure}
                  onChange={(e) => setCohortMeasure(e.target.value)}
                  className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                >
                  <option value="">(optional)</option>
                  {fields.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name} · {f.ttype}
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}
          {viewType === "grid" && (
            <>
              <label className="text-sm">
                <span className="text-muted">row_field</span>
                <select
                  value={gridRowField}
                  onChange={(e) => setGridRowField(e.target.value)}
                  className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                  data-testid="designer-grid-row-field"
                >
                  <option value="">(optional)</option>
                  {fields.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name} · {f.ttype}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="text-muted">col_field</span>
                <select
                  value={gridColField}
                  onChange={(e) => setGridColField(e.target.value)}
                  className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                  data-testid="designer-grid-col-field"
                >
                  <option value="">(optional)</option>
                  {dateFieldsForSelect.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name} · {f.ttype}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="text-muted">measure</span>
                <select
                  value={gridMeasure}
                  onChange={(e) => setGridMeasure(e.target.value)}
                  className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                  data-testid="designer-grid-measure"
                >
                  <option value="">(optional)</option>
                  {fields
                    .filter(
                      (f) =>
                        f.ttype === "integer" ||
                        f.ttype === "float" ||
                        f.ttype === "monetary",
                    )
                    .map((f) => (
                      <option key={f.id} value={f.name}>
                        {f.name} · {f.ttype}
                      </option>
                    ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="text-muted">adjustment</span>
                <select
                  value={gridAdjustment}
                  onChange={(e) => setGridAdjustment(e.target.value)}
                  className="mt-1 block border border-border-subtle bg-surface px-3 py-2 text-sm"
                  data-testid="designer-grid-adjustment"
                >
                  <option value="">(optional)</option>
                  <option value="increment">increment</option>
                  <option value="value">value</option>
                </select>
              </label>
              <label className="text-sm">
                <span className="text-muted">date_start</span>
                <select
                  value={gridDateStart}
                  onChange={(e) => setGridDateStart(e.target.value)}
                  className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                >
                  <option value="">(optional)</option>
                  {dateFieldsForSelect.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="text-muted">date_stop</span>
                <select
                  value={gridDateStop}
                  onChange={(e) => setGridDateStop(e.target.value)}
                  className="mt-1 block border border-border-subtle bg-surface px-3 py-2 font-mono text-sm"
                >
                  <option value="">(optional)</option>
                  {dateFieldsForSelect.map((f) => (
                    <option key={f.id} value={f.name}>
                      {f.name}
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}
              </div>
            </details>
          )}
          <label className="text-sm">
            <span className="text-muted">Title</span>
            <input
              value={title}
              onChange={(e) => {
                pendingCoalesceRef.current = "title";
                pendingHistoryLabelRef.current = "Edit title";
                setTitle(e.target.value);
              }}
              className="mt-1 block w-48 border border-border-subtle bg-surface px-3 py-2"
            />
          </label>
          <label className="text-sm">
            <span className="text-muted">Save strategy</span>
            <select
              value={saveStrategy}
              onChange={(e) => setSaveStrategy(e.target.value as "inherit" | "overwrite")}
              className="mt-1 block w-40 border border-border-subtle bg-surface px-2 py-2 text-sm"
            >
              <option value="inherit">Inherit (safe)</option>
              <option value="overwrite">Overwrite primary</option>
            </select>
          </label>
          <button
            type="button"
            disabled={busy || !model}
            onClick={() => void onSave()}
            className="h-10 bg-accent px-5 text-sm font-semibold text-on-accent disabled:opacity-60"
          >
            {busy ? "Saving…" : archOverride ? "Save arch override" : "Save to Odoo"}
          </button>
          {!model.startsWith("x_") && viewType === "form" ? (
            <>
              <button
                type="button"
                disabled={busy || !model}
                onClick={() => void onRepairDuplicateChrome()}
                className="h-10 border border-border-subtle px-4 text-sm text-muted disabled:opacity-40"
                data-testid="designer-fix-duplicate-chrome"
                title="Rewrites account.move.designer.form (etc.) from full form replace to additive x_* only"
              >
                Fix duplicate chrome
              </button>
              <button
                type="button"
                disabled={busy || !model}
                onClick={() => setConfirmUnlinkInheritOpen(true)}
                className="h-10 border border-danger/50 px-4 text-sm text-danger disabled:opacity-40"
                data-testid="designer-unlink-inherit"
                title="Deletes {model}.designer.form inherit — restores stock toolbar/tabs"
              >
                Unlink designer inherit
              </button>
            </>
          ) : null}
          <button
            type="button"
            disabled={busy || !model}
            onClick={async () => {
              setBusy(true); setError(null);
              try {
                const out = await api.polishForm(connectionId, model, title);
                setNotice(out.applied ? `Polished form for ${model}` : `Polish skipped: ${JSON.stringify(out.detail)}`);
                await loadExistingView();
              } catch (err) {
                setError(err instanceof Error ? err.message : "Polish failed");
              } finally { setBusy(false); }
            }}
            className="h-10 border border-border-subtle px-4 text-sm text-muted disabled:opacity-40"
          >
            Polish form layout
          </button>
        </Card>
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

        {(viewType === "calendar" ||
          viewType === "graph" ||
          viewType === "pivot" ||
          viewType === "map" ||
          viewType === "activity" ||
          viewType === "gantt" ||
          viewType === "cohort" ||
          viewType === "grid") &&
          model && (
          <div className="mt-6 border border-border-subtle bg-surface-muted p-4">
            <h2 className="mb-2 text-sm font-semibold text-ink">
              {viewType} view fields
            </h2>
            <p className="mb-3 text-xs text-muted">
              Arch preview updates from these fields. Drag from the palette into
              form/list is unchanged — use the buttons below for reporting axes.
            </p>
            {viewType === "map" && (
              <p className="mb-3 border border-warning/40 bg-warning-subtle px-3 py-2 text-xs text-warning">
                Map views need a <code className="text-muted">res.partner</code>{" "}
                many2one (<code className="text-muted">res_partner</code> attr).
                Without a partner field, Odoo will not render the map.
              </p>
            )}
            {viewType === "gantt" && (
              <p className="mb-3 border border-warning/40 bg-warning-subtle px-3 py-2 text-xs text-warning">
                Gantt arch is Community-safe metadata, but the client often needs{" "}
                <code className="text-muted">web_gantt</code> /{" "}
                <code className="text-muted">project</code> (Enterprise or installed
                modules). We do not claim EE live — save may succeed while Open in Odoo
                shows nothing without the module.
              </p>
            )}
            {viewType === "cohort" && (
              <p className="mb-3 border border-warning/40 bg-warning-subtle px-3 py-2 text-xs text-warning">
                Cohort views are module/version gated. Arch can be saved via public RPC;
                the UI may be unavailable without the cohort client module. Not an EE
                live claim.
              </p>
            )}
            {viewType === "grid" && (
              <p className="mb-3 border border-warning/40 bg-warning-subtle px-3 py-2 text-xs text-warning">
                Grid/planning views are Enterprise-gated. Arch emission is supported; live
                Open in Odoo requires EE modules on the instance.
              </p>
            )}
            {viewType === "calendar" && (
              <ul className="space-y-1 font-mono text-sm text-muted">
                {calendarFields.map((f) => (
                  <li key={f.id} className="flex items-center justify-between gap-2">
                    <span>{f.name}</span>
                    <button
                      type="button"
                      className="text-xs text-danger"
                      onClick={() =>
                        setCalendarFields((cols) => cols.filter((c) => c.id !== f.id))
                      }
                    >
                      Remove
                    </button>
                  </li>
                ))}
                {!calendarFields.length && (
                  <li className="text-muted">No display fields yet</li>
                )}
              </ul>
            )}
            {(viewType === "map" ||
              viewType === "activity" ||
              viewType === "gantt" ||
              viewType === "grid") && (
              <ul className="space-y-1 font-mono text-sm text-muted">
                {(viewType === "map"
                  ? mapFields
                  : viewType === "activity"
                    ? activityFields
                    : viewType === "gantt"
                      ? ganttFields
                      : gridFields
                ).map((f) => (
                  <li key={f.id} className="flex items-center justify-between gap-2">
                    <span>{f.name}</span>
                    <button
                      type="button"
                      className="text-xs text-danger"
                      onClick={() => {
                        if (viewType === "map") {
                          setMapFields((cols) => cols.filter((c) => c.id !== f.id));
                        } else if (viewType === "activity") {
                          setActivityFields((cols) => cols.filter((c) => c.id !== f.id));
                        } else if (viewType === "gantt") {
                          setGanttFields((cols) => cols.filter((c) => c.id !== f.id));
                        } else {
                          setGridFields((cols) => cols.filter((c) => c.id !== f.id));
                        }
                      }}
                    >
                      Remove
                    </button>
                  </li>
                ))}
                {(viewType === "map"
                  ? mapFields
                  : viewType === "activity"
                    ? activityFields
                    : viewType === "gantt"
                      ? ganttFields
                      : gridFields
                ).length === 0 && (
                  <li className="text-muted">No display fields yet</li>
                )}
              </ul>
            )}
            {viewType === "cohort" && (
              <p className="text-xs text-muted">
                Cohort uses date_start / measure from the toolbar — no field list required.
              </p>
            )}
            {viewType === "graph" && (
              <ul className="space-y-2 font-mono text-sm text-muted">
                {graphFields.map((f) => (
                  <li key={f.id} className="flex flex-wrap items-center gap-2">
                    <span className="min-w-[8rem]">{f.name}</span>
                    <select
                      value={f.type ?? ""}
                      onChange={(e) => {
                        const next = e.target.value as "" | "row" | "measure";
                        setGraphFields((cols) =>
                          cols.map((c) =>
                            c.id === f.id
                              ? {
                                  ...c,
                                  type: next === "" ? undefined : next,
                                }
                              : c,
                          ),
                        );
                      }}
                      className="border border-border-subtle bg-surface px-2 py-1 text-xs"
                    >
                      <option value="">(role)</option>
                      <option value="row">row</option>
                      <option value="measure">measure</option>
                    </select>
                    <button
                      type="button"
                      className="text-xs text-danger"
                      onClick={() =>
                        setGraphFields((cols) => cols.filter((c) => c.id !== f.id))
                      }
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {viewType === "pivot" && (
              <ul className="space-y-2 font-mono text-sm text-muted">
                {pivotFields.map((f) => (
                  <li key={f.id} className="flex flex-wrap items-center gap-2">
                    <span className="min-w-[8rem]">{f.name}</span>
                    <select
                      value={f.type ?? ""}
                      onChange={(e) => {
                        const next = e.target.value as "" | "row" | "col" | "measure";
                        setPivotFields((cols) =>
                          cols.map((c) =>
                            c.id === f.id
                              ? {
                                  ...c,
                                  type: next === "" ? undefined : next,
                                }
                              : c,
                          ),
                        );
                      }}
                      className="border border-border-subtle bg-surface px-2 py-1 text-xs"
                    >
                      <option value="">(role)</option>
                      <option value="row">row</option>
                      <option value="col">col</option>
                      <option value="measure">measure</option>
                    </select>
                    {f.type === "col" && (
                      <input
                        value={f.interval ?? ""}
                        placeholder="interval"
                        onChange={(e) =>
                          setPivotFields((cols) =>
                            cols.map((c) =>
                              c.id === f.id
                                ? { ...c, interval: e.target.value || undefined }
                                : c,
                            ),
                          )
                        }
                        className="w-24 border border-border-subtle bg-surface px-2 py-1 text-xs"
                      />
                    )}
                    <button
                      type="button"
                      className="text-xs text-danger"
                      onClick={() =>
                        setPivotFields((cols) => cols.filter((c) => c.id !== f.id))
                      }
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {viewType !== "cohort" && (
            <div className="mt-3 space-y-2">
              <p className="text-[11px] text-muted">
                Click <span className="font-mono text-muted">+ field</span> to include an
                existing model field. Custom <span className="font-mono">x_*</span> fields are
                listed first (do not use Create field — that creates new columns).
              </p>
              <div className="flex max-h-40 flex-wrap gap-2 overflow-y-auto">
              {[...fields]
                .sort((a, b) => {
                  const rank = (n: string) =>
                    n.startsWith("x_") ? 0 : n.startsWith("activity_") ? 2 : 1;
                  const d = rank(a.name) - rank(b.name);
                  return d !== 0 ? d : a.name.localeCompare(b.name);
                })
                .map((f) => (
                <button
                  key={f.id}
                  type="button"
                  className="border border-border-subtle px-2 py-0.5 font-mono text-[11px] text-muted"
                  onClick={() => {
                    const nextField: DesignerField = {
                      kind: "field",
                      id: uid("f"),
                      name: f.name,
                      string: f.field_description,
                    };
                    if (viewType === "calendar") {
                      setCalendarFields((cols) =>
                        cols.some((c) => c.name === f.name) ? cols : [...cols, nextField],
                      );
                    } else if (viewType === "map") {
                      setMapFields((cols) =>
                        cols.some((c) => c.name === f.name) ? cols : [...cols, nextField],
                      );
                    } else if (viewType === "activity") {
                      setActivityFields((cols) =>
                        cols.some((c) => c.name === f.name) ? cols : [...cols, nextField],
                      );
                    } else if (viewType === "gantt") {
                      setGanttFields((cols) =>
                        cols.some((c) => c.name === f.name) ? cols : [...cols, nextField],
                      );
                    } else if (viewType === "grid") {
                      setGridFields((cols) =>
                        cols.some((c) => c.name === f.name) ? cols : [...cols, nextField],
                      );
                    } else if (viewType === "graph") {
                      setGraphFields((cols) =>
                        cols.some((c) => c.name === f.name)
                          ? cols
                          : [
                              ...cols,
                              {
                                id: uid("af"),
                                name: f.name,
                                type: "measure",
                                string: f.field_description,
                              },
                            ],
                      );
                    } else {
                      setPivotFields((cols) =>
                        cols.some((c) => c.name === f.name)
                          ? cols
                          : [
                              ...cols,
                              {
                                id: uid("af"),
                                name: f.name,
                                type: "row",
                                string: f.field_description,
                              },
                            ],
                      );
                    }
                  }}
                >
                  + {f.name}
                </button>
              ))}
              </div>
            </div>
            )}
          </div>
        )}

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
