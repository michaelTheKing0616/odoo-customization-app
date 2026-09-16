"use client";

import type { Dispatch, SetStateAction } from "react";
import { FormCanvas } from "@/components/designer/FormCanvas";
import { KanbanCardPreview } from "@/components/designer/KanbanCardPreview";
import { PreviewThemeScope } from "@/components/designer/PreviewThemeScope";
import {
  OdooControlPanel,
  OdooKanbanView,
  OdooListView,
  OdooPreviewScope,
} from "@/components/odoo-preview";
import type { FieldRow, PreviewTheme } from "@/lib/api";
import {
  resolveFieldLabel,
  type DesignerButton,
  type DesignerField,
  type DesignerGroup,
  type DesignerNotebook,
  type FormChild,
  type SelectedField,
  type ViewType,
} from "@/components/designer/designer-model";
import type { DesignerRailTabId } from "@/components/designer/DesignerToolsRail";

export type DesignerStructuralCanvasProps = {
  viewType: ViewType;
  model: string;
  title: string;
  fields: FieldRow[];
  previewTheme: PreviewTheme | null;
  formChildren: FormChild[];
  headerButtons: DesignerButton[];
  buttonBox: DesignerButton[];
  statusbarField: string;
  statusbarVisible: string;
  canvasFlashId: string | null;
  selected: SelectedField | null;
  setSelected: Dispatch<SetStateAction<SelectedField | null>>;
  setRailTab: (v: DesignerRailTabId) => void;
  listColumns: DesignerField[];
  listDecorationDanger: string;
  listDecorationInfo: string;
  listDecorationMuted: string;
  kanbanFields: DesignerField[];
  kanbanGroupBy: string;
  setKanbanFields: Dispatch<SetStateAction<DesignerField[]>>;
  selectCanvasField: (fieldId: string) => void;
  addFieldToGroup: (groupId: string, fieldName: string, index?: number) => void;
  dropFieldOnPage: (
    notebookId: string,
    pageId: string,
    fieldName: string,
    index?: number,
  ) => void;
  reorderFormNode: (
    fieldId: string,
    target:
      | { kind: "group"; groupId: string }
      | { kind: "page"; notebookId: string; pageId: string },
    index: number,
  ) => void;
  setFormChildren: Dispatch<SetStateAction<FormChild[]>>;
  moveKanbanField: (fieldId: string, dir: -1 | 1) => void;
  addKanbanField: (fieldName: string) => void;
};

export function DesignerStructuralCanvas(props: DesignerStructuralCanvasProps) {
  const {
    viewType,
    model,
    title,
    fields,
    previewTheme,
    formChildren,
    headerButtons,
    buttonBox,
    statusbarField,
    statusbarVisible,
    canvasFlashId,
    selected,
    setSelected,
    setRailTab,
    listColumns,
    listDecorationDanger,
    listDecorationInfo,
    listDecorationMuted,
    kanbanFields,
    kanbanGroupBy,
    setKanbanFields,
    selectCanvasField,
    addFieldToGroup,
    dropFieldOnPage,
    reorderFormNode,
    setFormChildren,
    moveKanbanField,
    addKanbanField,
  } = props;

  const formStructuralCanvas = (
    <OdooPreviewScope showBanner previewVars={previewTheme?.preview_vars}>
      <div data-testid="designer-form-layout">
        <OdooControlPanel
          breadcrumb={`View Designer › ${title || model}`}
          activeView="form"
          availableViews={["form"]}
          showSearchPlaceholder
        />
        <FormCanvas
          title={title || model}
          statusbar={statusbarField || null}
          statusbarVisible={statusbarVisible || null}
          groupLayout={
            formChildren.filter((c) => c.kind === "group").length >= 2
              ? "two-column"
              : "stack"
          }
          headerButtons={headerButtons.map((b) => ({
            id: b.id,
            string: b.string || "Button",
          }))}
          smartButtons={buttonBox.map((b) => ({ id: b.id, string: b.string || "Smart" }))}
          flashId={canvasFlashId}
          groups={formChildren
            .filter((c): c is DesignerGroup => c.kind === "group")
            .map((g) => ({
              id: g.id,
              string: g.string,
              fields: g.children
                .filter((n): n is DesignerField => n.kind === "field")
                .map((f) => {
                  const meta = fields.find((row) => row.name === f.name);
                  return {
                    id: f.id,
                    name: f.name,
                    string: resolveFieldLabel(f.name, f.string, fields),
                    ttype: meta?.ttype,
                    widget: f.widget,
                    required: f.required === true,
                  };
                }),
            }))}
          notebooks={formChildren
            .filter((c): c is DesignerNotebook => c.kind === "notebook")
            .map((nb) => ({
              id: nb.id,
              pages: nb.pages.map((p) => ({
                id: p.id,
                string: p.string,
                fields: p.children
                  .filter((n): n is DesignerField => n.kind === "field")
                  .map((f) => {
                    const meta = fields.find((row) => row.name === f.name);
                    return {
                      id: f.id,
                      name: f.name,
                      string: resolveFieldLabel(f.name, f.string, fields),
                      ttype: meta?.ttype,
                      widget: f.widget,
                      required: f.required === true,
                    };
                  }),
              })),
            }))}
          selectedFieldId={
            selected?.scope === "form-group" || selected?.scope === "form-page"
              ? selected.fieldId
              : null
          }
          onSelectField={selectCanvasField}
          onMoveField={(fieldId, dir) => {
            setFormChildren((children) =>
              children.map((child) => {
                if (child.kind !== "group") return child;
                const idx = child.children.findIndex(
                  (n) => n.kind === "field" && n.id === fieldId,
                );
                if (idx < 0) return child;
                const next = idx + dir;
                if (next < 0 || next >= child.children.length) return child;
                const copy = [...child.children];
                const [item] = copy.splice(idx, 1);
                copy.splice(next, 0, item);
                return { ...child, children: copy };
              }),
            );
          }}
          onDropFieldName={(groupId, fieldName, index) => {
            addFieldToGroup(groupId, fieldName, index);
          }}
          onDropFieldOnPage={(notebookId, pageId, fieldName, index) => {
            dropFieldOnPage(notebookId, pageId, fieldName, index);
          }}
          onReorderField={(fieldId, groupId, index) =>
            reorderFormNode(fieldId, { kind: "group", groupId }, index)
          }
          onReorderPageField={(fieldId, notebookId, pageId, index) =>
            reorderFormNode(fieldId, { kind: "page", notebookId, pageId }, index)
          }
        />
      </div>
    </OdooPreviewScope>
  );

  const listStructuralCanvas = (
    <div data-testid="designer-list-layout">
      <OdooPreviewScope showBanner={false} previewVars={previewTheme?.preview_vars}>
        <OdooListView
          view={{
            type: "list",
            model: model || "model",
            title: title || model,
            columns: listColumns.map((f) => ({
              id: f.id,
              name: f.name,
              string: resolveFieldLabel(f.name, f.string, fields) || f.name,
            })),
            decorations: {
              danger: listDecorationDanger || null,
              info: listDecorationInfo || null,
              muted: listDecorationMuted || null,
            },
          }}
        />
      </OdooPreviewScope>
    </div>
  );

  const kanbanStructuralCanvas = (
    <div data-testid="designer-kanban-layout">
      <PreviewThemeScope previewVars={previewTheme?.preview_vars}>
        <OdooKanbanView
          view={{
            type: "kanban",
            model: model || "model",
            title: title || model,
            groupBy: kanbanGroupBy || null,
            cardFields: kanbanFields.map((f) => ({
              id: f.id,
              name: f.name,
              string: f.string || f.name,
            })),
          }}
        />
        <div className="mt-4">
          <KanbanCardPreview
            title={title || model}
            groupBy={kanbanGroupBy || null}
            fields={kanbanFields.map((f) => ({
              id: f.id,
              name: f.name,
              string: f.string,
            }))}
            selectedFieldId={selected?.scope === "kanban" ? selected.fieldId : null}
            onSelectField={(fieldId) => {
              setSelected({ scope: "kanban", fieldId });
              setRailTab("properties");
            }}
            onMoveField={moveKanbanField}
            onRemoveField={(fieldId) => {
              setKanbanFields((cols) => cols.filter((c) => c.id !== fieldId));
              setSelected((sel) =>
                sel?.scope === "kanban" && sel.fieldId === fieldId ? null : sel,
              );
            }}
            onDropFieldName={(fieldName) => addKanbanField(fieldName)}
          />
        </div>
      </PreviewThemeScope>
    </div>
  );

  return (
    viewType === "form"
      ? formStructuralCanvas
      : viewType === "list"
        ? listStructuralCanvas
        : viewType === "kanban"
          ? kanbanStructuralCanvas
          : (
            <div className="rounded-md border border-border-subtle bg-surface p-4 text-sm text-muted">
              Layout canvas for {viewType} uses the Structure tab. Live Odoo remains
              the authoritative preview.
            </div>
          )
  );
}
