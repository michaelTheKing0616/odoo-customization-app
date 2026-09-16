"use client";

import { useMemo } from "react";
import type { FieldRow } from "@/lib/api";
import {
  fieldSpec,
  nodeSpec,
  resolveFieldLabel,
  sortedDateFields,
  type AxisDesignerField,
  type DesignerButton,
  type DesignerField,
  type FormChild,
  type SearchFilter,
  type SearchGroupByFilter,
  type ViewType,
} from "@/components/designer/designer-model";

export type DesignerViewSpecsInput = {
  viewType: ViewType;
  title: string;
  fields: FieldRow[];
  formChildren: FormChild[];
  headerButtons: DesignerButton[];
  buttonBox: DesignerButton[];
  statusbarField: string;
  statusbarVisible: string;
  formCanCreate: boolean;
  formCanEdit: boolean;
  formCanDelete: boolean;
  formCanDuplicate: boolean;
  listColumns: DesignerField[];
  listDecorationDanger: string;
  listDecorationInfo: string;
  listDecorationMuted: string;
  listCanCreate: boolean;
  listCanEdit: boolean;
  listCanDelete: boolean;
  listMultiEdit: boolean;
  listDefaultOrder: string;
  viewSample: boolean;
  searchFields: DesignerField[];
  searchFilters: SearchFilter[];
  searchGroupByFilters: SearchGroupByFilter[];
  kanbanFields: DesignerField[];
  kanbanGroupBy: string;
  kanbanCanCreate: boolean;
  kanbanQuickCreate: boolean;
  calendarDateStart: string;
  calendarDateStop: string;
  calendarColor: string;
  calendarMode: string;
  calendarFields: DesignerField[];
  graphType: "bar" | "line" | "pie";
  graphFields: AxisDesignerField[];
  pivotFields: AxisDesignerField[];
  mapResPartner: string;
  mapRouting: boolean;
  mapFields: DesignerField[];
  activityFields: DesignerField[];
  ganttDateStart: string;
  ganttDateStop: string;
  ganttGroupBy: string;
  ganttColor: string;
  ganttProgress: string;
  ganttDefaultScale: string;
  ganttDependencyField: string;
  ganttFields: DesignerField[];
  gridRowField: string;
  gridColField: string;
  gridMeasure: string;
  gridAdjustment: string;
  gridDateStart: string;
  gridDateStop: string;
  gridFields: DesignerField[];
  cohortDateStart: string;
  cohortDateStop: string;
  cohortInterval: "day" | "week" | "month" | "year" | "";
  cohortMode: "retention" | "churn" | "";
  cohortTimeline: "forward" | "backward" | "";
  cohortMeasure: string;
};

export function useDesignerViewSpecs(input: DesignerViewSpecsInput) {
  const {
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
  } = input;

  const formSpec = useMemo(
    () => ({
      string: title,
      create: formCanCreate,
      edit: formCanEdit,
      delete: formCanDelete,
      duplicate: formCanDuplicate,
      statusbar_field: statusbarField || null,
      statusbar_visible: statusbarVisible || null,
      header_buttons: headerButtons.map((b) => nodeSpec(b)),
      button_box: buttonBox.map((b) => nodeSpec(b)),
      children: formChildren.map((child) => {
        if (child.kind === "group") {
          return {
            kind: "group",
            string: child.string,
            children: child.children
              .filter((n) => n.kind === "button" || (n.kind === "field" && n.name.trim()))
              .map((n) => {
              if (n.kind === "button") return nodeSpec(n);
              return fieldSpec({
                ...n,
                string: resolveFieldLabel(n.name, n.string, fields),
              });
            }),
          };
        }
        return {
          kind: "notebook",
          pages: child.pages.map((p) => ({
            string: p.string,
            children: p.children
              .filter((n) => n.kind === "button" || (n.kind === "field" && n.name.trim()))
              .map((n) => {
              if (n.kind === "button") return nodeSpec(n);
              return fieldSpec({
                ...n,
                string: resolveFieldLabel(n.name, n.string, fields),
              });
            }),
          })),
        };
      }),
    }),
    [
      formChildren,
      fields,
      title,
      headerButtons,
      buttonBox,
      statusbarField,
      statusbarVisible,
      formCanCreate,
      formCanEdit,
      formCanDelete,
      formCanDuplicate,
    ],
  );

  const listSpec = useMemo(
    () => ({
      string: title,
      create: listCanCreate,
      edit: listCanEdit,
      delete: listCanDelete,
      multi_edit: listMultiEdit,
      default_order: listDefaultOrder || null,
      sample: viewSample || null,
      columns: listColumns.map(fieldSpec),
      decoration_danger: listDecorationDanger || null,
      decoration_info: listDecorationInfo || null,
      decoration_muted: listDecorationMuted || null,
    }),
    [
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
      title,
    ],
  );

  const searchSpec = useMemo(
    () => ({
      string: title,
      fields: searchFields.map(fieldSpec),
      filters: searchFilters.map((f) => ({
        kind: "filter" as const,
        name: f.name,
        string: f.string,
        domain: f.domain,
      })),
      group_by_filters: searchGroupByFilters.map((f) => ({
        kind: "filter" as const,
        name: f.name,
        string: f.string,
        context: f.context || undefined,
      })),
    }),
    [searchFields, searchFilters, searchGroupByFilters, title],
  );

  const kanbanSpec = useMemo(
    () => ({
      string: title,
      records_fields: kanbanFields.map((f) => f.name),
      default_group_by: kanbanGroupBy || null,
      create: kanbanCanCreate,
      quick_create: kanbanQuickCreate,
      sample: viewSample || null,
    }),
    [kanbanFields, kanbanGroupBy, kanbanCanCreate, kanbanQuickCreate, viewSample, title],
  );

  const calendarSpec = useMemo(
    () => ({
      string: title,
      date_start: calendarDateStart || "date",
      date_stop: calendarDateStop || null,
      color: calendarColor || null,
      mode: calendarMode || null,
      fields: calendarFields.map((f) => fieldSpec(f)),
    }),
    [calendarColor, calendarDateStart, calendarDateStop, calendarFields, calendarMode, title],
  );

  const dateFieldsForSelect = useMemo(() => sortedDateFields(fields), [fields]);

  const graphSpec = useMemo(
    () => ({
      string: title,
      type: graphType,
      sample: viewSample || null,
      fields: graphFields.map((f) => ({
        kind: "field" as const,
        name: f.name,
        type: f.type,
        interval: f.interval || undefined,
        string: f.string,
      })),
    }),
    [graphFields, graphType, viewSample, title],
  );

  const pivotSpec = useMemo(
    () => ({
      string: title,
      sample: viewSample || null,
      fields: pivotFields.map((f) => ({
        kind: "field" as const,
        name: f.name,
        type: f.type,
        interval: f.interval || undefined,
        string: f.string,
      })),
    }),
    [pivotFields, viewSample, title],
  );

  const mapSpec = useMemo(
    () => ({
      string: title,
      res_partner: mapResPartner || null,
      routing: mapRouting ? true : null,
      fields: mapFields.map((f) => fieldSpec(f)),
    }),
    [mapFields, mapResPartner, mapRouting, title],
  );

  const activitySpec = useMemo(
    () => ({
      string: title,
      fields: activityFields.map((f) => fieldSpec(f)),
    }),
    [activityFields, title],
  );

  const ganttSpec = useMemo(
    () => ({
      string: title,
      date_start: ganttDateStart || "date_start",
      date_stop: ganttDateStop || null,
      default_group_by: ganttGroupBy || null,
      default_scale: ganttDefaultScale || null,
      dependency_field: ganttDependencyField || null,
      color: ganttColor || null,
      progress: ganttProgress || null,
      fields: ganttFields.map((f) => fieldSpec(f)),
    }),
    [
      ganttColor,
      ganttDateStart,
      ganttDateStop,
      ganttDefaultScale,
      ganttDependencyField,
      ganttFields,
      ganttGroupBy,
      ganttProgress,
      title,
    ],
  );

  const gridSpec = useMemo(
    () => ({
      string: title,
      row_field: gridRowField || null,
      col_field: gridColField || null,
      measure: gridMeasure || null,
      adjustment: gridAdjustment || null,
      date_start: gridDateStart || null,
      date_stop: gridDateStop || null,
      fields: gridFields.map((f) => fieldSpec(f)),
    }),
    [
      gridAdjustment,
      gridColField,
      gridDateStart,
      gridDateStop,
      gridFields,
      gridMeasure,
      gridRowField,
      title,
    ],
  );

  const cohortSpec = useMemo(
    () => ({
      string: title,
      date_start: cohortDateStart || "create_date",
      date_stop: cohortDateStop || null,
      interval: cohortInterval || null,
      mode: cohortMode || null,
      timeline: cohortTimeline || null,
      measure: cohortMeasure || null,
    }),
    [
      cohortDateStart,
      cohortDateStop,
      cohortInterval,
      cohortMeasure,
      cohortMode,
      cohortTimeline,
      title,
    ],
  );

  const activeViewSpec = useMemo(() => {
    if (viewType === "form") return formSpec;
    if (viewType === "list") return listSpec;
    if (viewType === "kanban") return kanbanSpec;
    if (viewType === "calendar") return calendarSpec;
    if (viewType === "graph") return graphSpec;
    if (viewType === "pivot") return pivotSpec;
    if (viewType === "map") return mapSpec;
    if (viewType === "activity") return activitySpec;
    if (viewType === "gantt") return ganttSpec;
    if (viewType === "cohort") return cohortSpec;
    if (viewType === "grid") return gridSpec;
    return searchSpec;
  }, [
    viewType,
    formSpec,
    listSpec,
    kanbanSpec,
    calendarSpec,
    graphSpec,
    pivotSpec,
    mapSpec,
    activitySpec,
    ganttSpec,
    cohortSpec,
    gridSpec,
    searchSpec,
  ]);

  return {
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
  };
}
