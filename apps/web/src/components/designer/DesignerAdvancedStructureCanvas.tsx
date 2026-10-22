"use client";

import type { Dispatch, DragEvent, SetStateAction } from "react";
import { DomainBuilder } from "@/components/DomainBuilder";
import { KanbanCardPreview } from "@/components/designer/KanbanCardPreview";
import { PreviewThemeScope } from "@/components/designer/PreviewThemeScope";
import {
  OdooListView,
  OdooPreviewScope,
} from "@/components/odoo-preview";
import type { Connection, FieldRow, PreviewTheme } from "@/lib/api";
import {
  connectionSupports,
  connectionUnsupportedReason,
} from "@/lib/capabilities";
import type {
  BindDialogMode,
  ButtonPlacement,
  DesignerButton,
  DesignerField,
  FormChild,
  SearchFilter,
  SearchGroupByFilter,
  SelectedField,
  ViewType,
} from "@/components/designer/designer-model";
import { resolveFieldLabel, uid } from "@/components/designer/designer-model";
import { ReorderableBlocks, moveIndex } from "@/components/ui/canvas/ReorderableBlocks";
import { ChevronDown, ChevronUp } from "@/components/ui/icons";
import {
  DesignerGrip,
  DesignerPointerGhost,
  useDesignerPointerGhost,
} from "@/components/designer/DesignerPointerGhost";

export type DesignerAdvancedStructureCanvasProps = {
  viewType: ViewType;
  connection: Connection | null;
  model: string;
  title: string;
  toolbarFlash: string | null;
  canvasFlashId: string | null;
  previewTheme: PreviewTheme | null;
  viewSample: boolean;
  setViewSample: (v: boolean) => void;
  formChildren: FormChild[];
  headerButtons: DesignerButton[];
  buttonBox: DesignerButton[];
  setHeaderButtons: Dispatch<SetStateAction<DesignerButton[]>>;
  setButtonBox: Dispatch<SetStateAction<DesignerButton[]>>;
  statusbarField: string;
  setStatusbarField: (v: string) => void;
  statusbarVisible: string;
  setStatusbarVisible: (v: string) => void;
  formCanCreate: boolean;
  formCanEdit: boolean;
  formCanDelete: boolean;
  formCanDuplicate: boolean;
  setFormCanCreate: (v: boolean) => void;
  setFormCanEdit: (v: boolean) => void;
  setFormCanDelete: (v: boolean) => void;
  setFormCanDuplicate: (v: boolean) => void;
  listColumns: DesignerField[];
  setListColumns: Dispatch<SetStateAction<DesignerField[]>>;
  listDecorationDanger: string;
  listDecorationInfo: string;
  listDecorationMuted: string;
  setListDecorationDanger: (v: string) => void;
  setListDecorationInfo: (v: string) => void;
  setListDecorationMuted: (v: string) => void;
  listCanCreate: boolean;
  listCanEdit: boolean;
  listCanDelete: boolean;
  listMultiEdit: boolean;
  listDefaultOrder: string;
  setListCanCreate: (v: boolean) => void;
  setListCanEdit: (v: boolean) => void;
  setListCanDelete: (v: boolean) => void;
  setListMultiEdit: (v: boolean) => void;
  setListDefaultOrder: (v: string) => void;
  searchFields: DesignerField[];
  setSearchFields: Dispatch<SetStateAction<DesignerField[]>>;
  searchFilters: SearchFilter[];
  setSearchFilters: Dispatch<SetStateAction<SearchFilter[]>>;
  searchGroupByFilters: SearchGroupByFilter[];
  setSearchGroupByFilters: Dispatch<SetStateAction<SearchGroupByFilter[]>>;
  editingFilterId: string | null;
  setEditingFilterId: Dispatch<SetStateAction<string | null>>;
  kanbanFields: DesignerField[];
  setKanbanFields: Dispatch<SetStateAction<DesignerField[]>>;
  kanbanGroupBy: string;
  kanbanCanCreate: boolean;
  kanbanQuickCreate: boolean;
  setKanbanCanCreate: (v: boolean) => void;
  setKanbanQuickCreate: (v: boolean) => void;
  moveKanbanField: (fieldId: string, dir: -1 | 1) => void;
  addKanbanField: (fieldName: string) => void;
  fields: FieldRow[];
  selected: SelectedField | null;
  setSelected: Dispatch<SetStateAction<SelectedField | null>>;
  addGroup: () => void;
  addNotebook: () => void;
  addButtonToFirstGroup: () => void;
  openBindDialog: (placement: ButtonPlacement, mode?: BindDialogMode) => void;
  dropOnGroup: (groupId: string, e?: DragEvent | null, index?: number) => void;
  dropOnPage: (notebookId: string, pageId: string, e?: DragEvent | null) => void;
  removeFormChild: (childId: string) => void;
  removeNotebookPage: (notebookId: string, pageId: string) => void;
  renameNotebookPage: (notebookId: string, pageId: string, string: string) => void;
  renameGroup: (groupId: string, string: string) => void;
  addPageToNotebook: (notebookId: string) => void;
  removeFormField: (
    container: "group" | "page",
    containerId: string,
    fieldId: string,
    notebookId?: string,
  ) => void;
  announceAction: (message: string, flashId?: string | null, toolbarKey?: string) => void;
};

/** Middle column of Advanced layout: form, list, search and kanban structure editors. */
export function DesignerAdvancedStructureCanvas({
  viewType,
  connection,
  model,
  title,
  toolbarFlash,
  canvasFlashId,
  previewTheme,
  viewSample,
  setViewSample,
  formChildren,
  headerButtons,
  buttonBox,
  setHeaderButtons,
  setButtonBox,
  statusbarField,
  setStatusbarField,
  statusbarVisible,
  setStatusbarVisible,
  formCanCreate,
  formCanEdit,
  formCanDelete,
  formCanDuplicate,
  setFormCanCreate,
  setFormCanEdit,
  setFormCanDelete,
  setFormCanDuplicate,
  listColumns,
  setListColumns,
  listDecorationDanger,
  listDecorationInfo,
  listDecorationMuted,
  setListDecorationDanger,
  setListDecorationInfo,
  setListDecorationMuted,
  listCanCreate,
  listCanEdit,
  listCanDelete,
  listMultiEdit,
  listDefaultOrder,
  setListCanCreate,
  setListCanEdit,
  setListCanDelete,
  setListMultiEdit,
  setListDefaultOrder,
  searchFields,
  setSearchFields,
  searchFilters,
  setSearchFilters,
  searchGroupByFilters,
  setSearchGroupByFilters,
  editingFilterId,
  setEditingFilterId,
  kanbanFields,
  setKanbanFields,
  kanbanGroupBy,
  kanbanCanCreate,
  kanbanQuickCreate,
  setKanbanCanCreate,
  setKanbanQuickCreate,
  moveKanbanField,
  addKanbanField,
  fields,
  selected,
  setSelected,
  addGroup,
  addNotebook,
  addButtonToFirstGroup,
  openBindDialog,
  dropOnGroup,
  dropOnPage,
  removeFormChild,
  removeNotebookPage,
  renameNotebookPage,
  renameGroup,
  addPageToNotebook,
  removeFormField,
  announceAction,
}: DesignerAdvancedStructureCanvasProps) {
  const trackGhost = useDesignerPointerGhost();
  return (
          <section className="designer-desk designer-structure-desk" data-testid="designer-structure-editor">
            <div className="mb-3">
              <h2 className="text-sm font-semibold text-[var(--dz-paper-ink)]">
                {viewType === "form"
                  ? "Form layout (primary)"
                  : viewType === "list" || viewType === "kanban" || viewType === "search"
                    ? `${viewType[0].toUpperCase()}${viewType.slice(1)} layout`
                    : "Layout editor"}
              </h2>
              {viewType === "form" && (
                <p className="mt-1 max-w-[62ch] text-xs text-[var(--dz-paper-muted)]">
                  Add a group, then drag a field from the list on the left onto that group. The
                  page auto-scrolls when you drag near the edge.
                </p>
              )}
            </div>
            <div className="mb-4 flex flex-wrap gap-2">
              {viewType === "form" && (
                <>
                  <button
                    type="button"
                    onClick={addGroup}
                    className={`designer-quiet-btn is-outline ${
                      toolbarFlash === "group" ? "is-flashed" : ""
                    }`}
                  >
                    {toolbarFlash === "group" ? "Group added" : "Add group"}
                  </button>
                  <button
                    type="button"
                    onClick={addNotebook}
                    className={`designer-quiet-btn is-outline ${
                      toolbarFlash === "notebook" ? "is-flashed" : ""
                    }`}
                  >
                    {toolbarFlash === "notebook" ? "Notebook added" : "Add notebook"}
                  </button>
                  <button
                    type="button"
                    disabled={!connectionSupports(connection, "object_write_update_path")}
                    title={
                      connectionUnsupportedReason(connection, "object_write_update_path") ??
                      undefined
                    }
                    onClick={() => {
                      openBindDialog("header", "create_update");
                      announceAction("Opening header button binder…", null, "header");
                    }}
                    className={`designer-quiet-btn is-outline ${
                      toolbarFlash === "header" ? "is-flashed" : ""
                    }`}
                  >
                    {toolbarFlash === "header" ? "Header binder opened" : "Add header button"}
                  </button>
                  <button
                    type="button"
                    disabled={!connectionSupports(connection, "smart_button_inherit_box")}
                    title={
                      connectionUnsupportedReason(connection, "smart_button_inherit_box") ??
                      undefined
                    }
                    onClick={() => {
                      openBindDialog("button_box", "create_smart");
                      announceAction("Opening smart button binder…", null, "smart");
                    }}
                    className={`designer-quiet-btn is-outline ${
                      toolbarFlash === "smart" ? "is-flashed" : ""
                    }`}
                  >
                    {toolbarFlash === "smart" ? "Smart binder opened" : "Add smart button"}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      addButtonToFirstGroup();
                      announceAction("Opening inline button binder…", null, "inline");
                    }}
                    className={`designer-quiet-btn is-outline ${
                      toolbarFlash === "inline" ? "is-flashed" : ""
                    }`}
                  >
                    {toolbarFlash === "inline" ? "Inline binder opened" : "Add inline button"}
                  </button>
                </>
              )}
            </div>

            {viewType === "form" && (
              <div className="mb-4 space-y-3">
                <div className="designer-structure-card designer-structure-flags">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={formCanCreate}
                      onChange={(e) => setFormCanCreate(e.target.checked)}
                    />
                    Can Create
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={formCanEdit}
                      onChange={(e) => setFormCanEdit(e.target.checked)}
                    />
                    Can Edit
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={formCanDelete}
                      onChange={(e) => setFormCanDelete(e.target.checked)}
                    />
                    Can Delete
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={formCanDuplicate}
                      onChange={(e) => setFormCanDuplicate(e.target.checked)}
                    />
                    Can Duplicate
                  </label>
                </div>
                <div className="designer-structure-card grid gap-3 sm:grid-cols-2">
                  <label className="designer-structure-label block">
                    Statusbar field (selection)
                    <select
                      value={statusbarField}
                      onChange={(e) => setStatusbarField(e.target.value)}
                      className="designer-structure-input mt-1 w-full font-mono"
                    >
                      <option value="">(none)</option>
                      {fields
                        .filter((f) => f.ttype === "selection" || f.ttype === "many2one")
                        .map((f) => (
                          <option key={f.id} value={f.name}>
                            {f.name} · {f.ttype}
                          </option>
                        ))}
                    </select>
                  </label>
                  <label className="designer-structure-label block">
                    statusbar_visible (comma-separated)
                    <input
                      value={statusbarVisible}
                      onChange={(e) => setStatusbarVisible(e.target.value)}
                      placeholder="draft,confirmed,done"
                      disabled={!statusbarField}
                      className="designer-structure-input mt-1 w-full font-mono disabled:opacity-40"
                    />
                  </label>
                </div>
                <div className="designer-structure-card">
                  <p className="designer-structure-label mb-2">Header buttons</p>
                  <ul className="space-y-1">
                    {headerButtons.map((b) => (
                      <li
                        key={b.id}
                        className="designer-structure-row"
                      >
                        <span className="min-w-0 truncate">
                          {b.string}{" "}
                          <span className="font-mono text-xs text-[var(--dz-paper-muted)]">
                            type={b.type || "action"} name={b.name || "?"}
                          </span>
                        </span>
                        <button
                          type="button"
                          className="designer-quiet-btn is-danger"
                          onClick={() =>
                            setHeaderButtons((all) => all.filter((x) => x.id !== b.id))
                          }
                        >
                          Remove
                        </button>
                      </li>
                    ))}
                    {headerButtons.length === 0 && (
                      <li className="designer-structure-empty">
                        Bound to real ir.actions.* via type=&quot;action&quot;.
                      </li>
                    )}
                  </ul>
                </div>
                <div className="designer-structure-card">
                  <p className="designer-structure-label mb-2">Smart button box</p>
                  <ul className="space-y-1">
                    {buttonBox.map((b) => (
                      <li
                        key={b.id}
                        className="designer-structure-row"
                      >
                        <span className="min-w-0 truncate">
                          {b.string}{" "}
                          <span className="font-mono text-xs text-[var(--dz-paper-muted)]">
                            {b.icon || "fa-list"} · action {b.name || "?"}
                            {b.count_field ? ` · count ${b.count_field}` : ""}
                          </span>
                        </span>
                        <button
                          type="button"
                          className="designer-quiet-btn is-danger"
                          onClick={() => setButtonBox((all) => all.filter((x) => x.id !== b.id))}
                        >
                          Remove
                        </button>
                      </li>
                    ))}
                    {buttonBox.length === 0 && (
                      <li className="designer-structure-empty">
                        Opens related records (window action + active_id domain).
                      </li>
                    )}
                  </ul>
                </div>
              </div>
            )}

            {viewType === "form" &&
              formChildren.map((child) => {
                if (child.kind === "group") {
                  return (
                    <div
                      key={child.id}
                      data-structure-id={child.id}
                      data-canvas-id={child.id}
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={(e) => {
                        e.preventDefault();
                        dropOnGroup(child.id, e);
                      }}
                      className={`designer-structure-card is-drop-zone ${
                        canvasFlashId === child.id ? "is-canvas-flash" : ""
                      }`}
                    >
                      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                        <label className="designer-structure-label flex min-w-0 flex-1 items-center gap-2">
                          Group
                          <input
                            value={child.string || ""}
                            onChange={(e) => renameGroup(child.id, e.target.value)}
                            className="designer-structure-input min-w-0 flex-1 font-sans font-normal tracking-normal"
                            placeholder="untitled"
                          />
                        </label>
                        <button
                          type="button"
                          className="designer-quiet-btn is-danger shrink-0"
                          onClick={() => removeFormChild(child.id)}
                        >
                          Remove group
                        </button>
                      </div>
                      <ul className="space-y-1">
                        {child.children.map((f) => (
                          <li
                            key={f.id}
                            className={`designer-structure-row ${
                              selected?.fieldId === f.id ? "is-selected" : ""
                            }`}
                          >
                            <button
                              type="button"
                              className="text-left"
                              onClick={() =>
                                setSelected({
                                  scope: "form-group",
                                  groupId: child.id,
                                  fieldId: f.id,
                                })
                              }
                            >
                              {f.kind === "button" ? (
                                <span>
                                  <span className="designer-row-kind">Button</span> {f.string}{" "}
                                  <span className="font-mono text-xs text-[var(--dz-paper-muted)]">
                                    {f.type || "action"}:{f.name || "?"}
                                  </span>
                                </span>
                              ) : (
                                <>
                                  <span>{resolveFieldLabel(f.name, f.string, fields) || f.name}</span>
                                  <span className="ml-2 font-mono text-xs text-[var(--dz-paper-muted)]">
                                    {f.name}
                                  </span>
                                </>
                              )}
                            </button>
                            <button
                              type="button"
                              className="designer-quiet-btn is-danger"
                              onClick={() => removeFormField("group", child.id, f.id)}
                            >
                              Remove
                            </button>
                          </li>
                        ))}
                        {child.children.length === 0 && (
                          <li className="designer-structure-empty">Drop fields here</li>
                        )}
                      </ul>
                    </div>
                  );
                }
                return (
                  <div
                    key={child.id}
                    data-structure-id={child.id}
                    data-canvas-id={child.id}
                    className={`designer-structure-card ${
                      canvasFlashId === child.id ? "is-canvas-flash" : ""
                    }`}
                  >
                    <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                      <p className="designer-structure-label">Notebook</p>
                      <div className="flex gap-1">
                        <button
                          type="button"
                          className="designer-quiet-btn is-outline"
                          onClick={() => addPageToNotebook(child.id)}
                        >
                          Add page
                        </button>
                        <button
                          type="button"
                          className="designer-quiet-btn is-danger"
                          onClick={() => removeFormChild(child.id)}
                        >
                          Remove notebook
                        </button>
                      </div>
                    </div>
                    {child.pages.map((page) => (
                      <div
                        key={page.id}
                        data-structure-id={page.id}
                        data-canvas-id={page.id}
                        onDragOver={(e) => e.preventDefault()}
                        onDrop={(e) => {
                          e.preventDefault();
                          dropOnPage(child.id, page.id, e);
                        }}
                        className={`designer-structure-card is-drop-zone mb-3 last:mb-0 ${
                          canvasFlashId === page.id ? "is-canvas-flash" : ""
                        }`}
                      >
                        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                          <label className="designer-structure-label flex min-w-0 flex-1 items-center gap-2">
                            Page
                            <input
                              value={page.string}
                              onChange={(e) =>
                                renameNotebookPage(child.id, page.id, e.target.value)
                              }
                              className="designer-structure-input min-w-0 flex-1 font-normal tracking-normal"
                              placeholder="Tab title"
                            />
                          </label>
                          <button
                            type="button"
                            className="designer-quiet-btn is-danger shrink-0"
                            onClick={() => removeNotebookPage(child.id, page.id)}
                          >
                            Remove page
                          </button>
                        </div>
                        <ul className="space-y-1">
                          {page.children.map((f) => (
                            <li
                              key={f.id}
                              className={`designer-structure-row ${
                                selected?.fieldId === f.id ? "is-selected" : ""
                              }`}
                            >
                              <button
                                type="button"
                                className="text-left"
                                onClick={() =>
                                  f.kind === "field"
                                    ? setSelected({
                                        scope: "form-page",
                                        notebookId: child.id,
                                        pageId: page.id,
                                        fieldId: f.id,
                                      })
                                    : undefined
                                }
                              >
                                {f.kind === "button" ? (
                                  <span><span className="designer-row-kind">Button</span> {f.string}</span>
                                ) : (
                                  <>
                                    <span>
                                      {resolveFieldLabel(f.name, f.string, fields) || f.name}
                                    </span>
                                    <span className="ml-2 font-mono text-xs text-[var(--dz-paper-muted)]">
                                      {f.name}
                                    </span>
                                  </>
                                )}
                              </button>
                              <button
                                type="button"
                                className="designer-quiet-btn is-danger"
                                onClick={() =>
                                  removeFormField("page", page.id, f.id, child.id)
                                }
                              >
                                Remove
                              </button>
                            </li>
                          ))}
                          {page.children.length === 0 && (
                            <li className="designer-structure-empty">Drop fields here</li>
                          )}
                        </ul>
                      </div>
                    ))}
                  </div>
                );
              })}

            {viewType === "list" && (
              <div className="designer-structure-card min-h-40">
                <div className="designer-structure-flags mb-4">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={listCanCreate}
                      onChange={(e) => setListCanCreate(e.target.checked)}
                    />
                    Can Create
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={listCanEdit}
                      onChange={(e) => setListCanEdit(e.target.checked)}
                    />
                    Can Edit
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={listCanDelete}
                      onChange={(e) => setListCanDelete(e.target.checked)}
                    />
                    Can Delete
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={listMultiEdit}
                      onChange={(e) => setListMultiEdit(e.target.checked)}
                    />
                    multi_edit
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={viewSample}
                      onChange={(e) => setViewSample(e.target.checked)}
                      data-testid="designer-view-sample"
                    />
                    sample data
                  </label>
                </div>
                <label className="designer-structure-label mb-3 block">
                  default_order (Sort By)
                  <input
                    value={listDefaultOrder}
                    onChange={(e) => setListDefaultOrder(e.target.value)}
                    placeholder="name asc, id desc"
                    className="designer-structure-input mt-1 w-full font-mono font-normal tracking-normal"
                  />
                </label>
                <div className="mb-3 grid gap-2 sm:grid-cols-3">
                  <label className="designer-structure-label block">
                    decoration-danger
                    <input
                      value={listDecorationDanger}
                      onChange={(e) => setListDecorationDanger(e.target.value)}
                      placeholder="not x_returned"
                      className="designer-structure-input mt-1 w-full font-mono font-normal tracking-normal"
                    />
                  </label>
                  <label className="designer-structure-label block">
                    decoration-info
                    <input
                      value={listDecorationInfo}
                      onChange={(e) => setListDecorationInfo(e.target.value)}
                      placeholder="x_priority == 'high'"
                      className="designer-structure-input mt-1 w-full font-mono font-normal tracking-normal"
                    />
                  </label>
                  <label className="designer-structure-label block">
                    decoration-muted
                    <input
                      value={listDecorationMuted}
                      onChange={(e) => setListDecorationMuted(e.target.value)}
                      placeholder="x_active == False"
                      className="designer-structure-input mt-1 w-full font-mono font-normal tracking-normal"
                    />
                  </label>
                </div>
                <p className="designer-structure-label mb-2">
                  List columns (click a field to add)
                </p>
                <ul className="space-y-1">
                  {listColumns.map((f, idx) => (
                    <li
                      key={f.id}
                      className={`designer-structure-row ${
                        selected?.fieldId === f.id ? "is-selected" : ""
                      }`}
                    >
                      <button
                        type="button"
                        className="text-left"
                        onClick={() => setSelected({ scope: "list", fieldId: f.id })}
                      >
                        <span className="tabular-nums text-[var(--dz-paper-muted)]">{idx + 1}.</span>{" "}
                        <span className="font-mono">{f.name}</span>
                      </button>
                      <button
                        type="button"
                        className="designer-quiet-btn is-danger"
                        onClick={() => {
                          setListColumns((cols) => cols.filter((c) => c.id !== f.id));
                          setSelected((sel) => (sel?.fieldId === f.id ? null : sel));
                        }}
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
                {listColumns.length > 0 ? (
                  <details className="designer-structure-card mt-4 mb-0" data-testid="designer-list-preview">
                    <summary className="cursor-pointer text-sm font-semibold">
                      Odoo-style list preview
                    </summary>
                    <div className="mt-3">
                      <OdooPreviewScope showBanner={false} previewVars={previewTheme?.preview_vars}>
                          <OdooListView
                            view={{
                              type: "list",
                              model: model,
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
                  </details>
                ) : null}
              </div>
            )}

            {viewType === "search" && (
              <div className="designer-structure-card min-h-40">
                <p className="designer-structure-label mb-2">Filters</p>
                <button
                  type="button"
                  className="designer-quiet-btn is-outline mb-3"
                  onClick={() =>
                    setSearchFilters((f) => [
                      ...f,
                      {
                        id: uid("sf"),
                        name: `filter_${f.length + 1}`,
                        string: `Filter ${f.length + 1}`,
                        domain: "[]",
                      },
                    ])
                  }
                >
                  Add search filter
                </button>
                {searchFilters.length > 0 && (
                  <ul className="mb-3 space-y-2 text-xs">
                    {searchFilters.map((f) => (
                      <li key={f.id} className="designer-structure-card mb-0 p-3">
                        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                          <input
                            value={f.string}
                            onChange={(e) =>
                              setSearchFilters((all) =>
                                all.map((x) =>
                                  x.id === f.id ? { ...x, string: e.target.value } : x,
                                ),
                              )
                            }
                            className="designer-structure-input min-w-[8rem] flex-1"
                          />
                          <button
                            type="button"
                            className="designer-quiet-btn"
                            onClick={() =>
                              setEditingFilterId((id) => (id === f.id ? null : f.id))
                            }
                          >
                            {editingFilterId === f.id ? "Hide domain" : "Edit domain"}
                          </button>
                          <button
                            type="button"
                            className="designer-quiet-btn is-danger"
                            onClick={() =>
                              setSearchFilters((all) => all.filter((x) => x.id !== f.id))
                            }
                          >
                            Remove
                          </button>
                        </div>
                        {editingFilterId === f.id ? (
                          <DomainBuilder
                            value={f.domain || "[]"}
                            onChange={(domain) =>
                              setSearchFilters((all) =>
                                all.map((x) => (x.id === f.id ? { ...x, domain } : x)),
                              )
                            }
                          />
                        ) : (
                          <span className="font-mono text-[var(--dz-paper-muted)]">{f.domain || "[]"}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
                <div className="designer-structure-card mb-3 p-3">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <p className="designer-structure-label">Group-by filters</p>
                    <button
                      type="button"
                      className="designer-quiet-btn is-outline"
                      onClick={() =>
                        setSearchGroupByFilters((f) => [
                          ...f,
                          {
                            id: uid("sg"),
                            name: `groupby_${f.length + 1}`,
                            string: `Group By ${f.length + 1}`,
                            context: "{'group_by': 'field'}",
                          },
                        ])
                      }
                    >
                      Add group-by filter
                    </button>
                  </div>
                  {searchGroupByFilters.length === 0 ? (
                    <p className="text-xs text-[var(--dz-paper-muted)]">
                      No group-by filters. Context example:{" "}
                      <code className="font-mono">{"{'group_by': 'x_stage'}"}</code>
                    </p>
                  ) : (
                    <ul className="space-y-2 text-xs text-[var(--dz-paper-muted)]">
                      {searchGroupByFilters.map((f) => (
                        <li key={f.id} className="grid gap-2 rounded-md bg-[var(--dz-lane)] p-2 sm:grid-cols-3">
                          <label className="block">
                            name
                            <input
                              value={f.name}
                              onChange={(e) =>
                                setSearchGroupByFilters((all) =>
                                  all.map((x) =>
                                    x.id === f.id ? { ...x, name: e.target.value } : x,
                                  ),
                                )
                              }
                              className="designer-structure-input mt-1 w-full font-mono font-normal tracking-normal"
                            />
                          </label>
                          <label className="block">
                            string
                            <input
                              value={f.string}
                              onChange={(e) =>
                                setSearchGroupByFilters((all) =>
                                  all.map((x) =>
                                    x.id === f.id ? { ...x, string: e.target.value } : x,
                                  ),
                                )
                              }
                              className="designer-structure-input mt-1 w-full font-normal tracking-normal"
                            />
                          </label>
                          <label className="block">
                            context
                            <input
                              value={f.context ?? ""}
                              onChange={(e) =>
                                setSearchGroupByFilters((all) =>
                                  all.map((x) =>
                                    x.id === f.id
                                      ? { ...x, context: e.target.value }
                                      : x,
                                  ),
                                )
                              }
                              placeholder="{'group_by': 'field'}"
                              className="designer-structure-input mt-1 w-full font-mono font-normal tracking-normal"
                            />
                          </label>
                          <button
                            type="button"
                            className="designer-quiet-btn is-danger justify-self-start sm:col-span-3"
                            onClick={() =>
                              setSearchGroupByFilters((all) =>
                                all.filter((x) => x.id !== f.id),
                              )
                            }
                          >
                            Remove
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <p className="designer-structure-label mb-2">
                  Search fields (click a field to add)
                </p>
                <ul className="space-y-1">
                  {searchFields.map((f, idx) => (
                    <li
                      key={f.id}
                      className={`designer-structure-row ${
                        selected?.fieldId === f.id ? "is-selected" : ""
                      }`}
                    >
                      <button
                        type="button"
                        className="text-left"
                        onClick={() => setSelected({ scope: "search", fieldId: f.id })}
                      >
                        <span className="tabular-nums text-[var(--dz-paper-muted)]">{idx + 1}.</span>{" "}
                        <span className="font-mono">{f.name}</span>
                      </button>
                      <button
                        type="button"
                        className="designer-quiet-btn is-danger"
                        onClick={() => {
                          setSearchFields((cols) => cols.filter((c) => c.id !== f.id));
                          setSelected((sel) => (sel?.fieldId === f.id ? null : sel));
                        }}
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {viewType === "kanban" && (
              <div className="min-h-40 space-y-4">
                <div className="designer-structure-card designer-structure-flags">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={kanbanCanCreate}
                      onChange={(e) => setKanbanCanCreate(e.target.checked)}
                    />
                    Can Create
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={kanbanQuickCreate}
                      onChange={(e) => setKanbanQuickCreate(e.target.checked)}
                    />
                    quick_create
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={viewSample}
                      onChange={(e) => setViewSample(e.target.checked)}
                      data-testid="designer-view-sample"
                    />
                    sample data
                  </label>
                </div>
                {!model && (
                  <KanbanCardPreview
                    title={title || "Kanban"}
                    groupBy={kanbanGroupBy || null}
                    fields={kanbanFields.map((f) => ({
                      id: f.id,
                      name: f.name,
                      string: f.string,
                    }))}
                    selectedFieldId={
                      selected?.scope === "kanban" ? selected.fieldId : null
                    }
                    onSelectField={(fieldId) =>
                      setSelected({ scope: "kanban", fieldId })
                    }
                    onMoveField={moveKanbanField}
                    onRemoveField={(fieldId) => {
                      setKanbanFields((cols) =>
                        cols.filter((c) => c.id !== fieldId),
                      );
                      setSelected((sel) =>
                        sel?.scope === "kanban" && sel.fieldId === fieldId
                          ? null
                          : sel,
                      );
                    }}
                    onDropFieldName={(fieldName) => addKanbanField(fieldName)}
                  />
                )}
                <div className="designer-structure-card mb-0">
                  <p className="designer-structure-label mb-2 flex flex-wrap items-center gap-2">
                    Card field order
                    {kanbanGroupBy ? (
                      <span className="designer-chip font-normal tracking-normal">
                        Grouped by <code className="font-mono">{kanbanGroupBy}</code>
                      </span>
                    ) : null}
                  </p>
                  <ReorderableBlocks
                    as="ul"
                    itemAs="li"
                    items={kanbanFields}
                    getId={(f) => f.id}
                    onMove={moveKanbanField}
                    onReorder={(from, to) => {
                      setKanbanFields((cols) => moveIndex(cols, from, to));
                    }}
                    className="space-y-1"
                    empty={
                      <li className="designer-structure-empty">
                        Click or drop fields from the palette to build the card.
                      </li>
                    }
                    itemProps={(f) => ({
                      "data-reorderable": "",
                      onPointerMove: trackGhost,
                      className: `designer-structure-row relative ${
                        selected?.scope === "kanban" && selected.fieldId === f.id
                          ? "is-selected"
                          : ""
                      }`,
                    })}
                  >
                    {(f, idx, meta) => (
                      <>
                        {meta.isDropTarget ? (
                          <span className="designer-drop-line" aria-hidden />
                        ) : null}
                        {meta.dropIndex === kanbanFields.length &&
                        idx === kanbanFields.length - 1 ? (
                          <span className="designer-drop-line is-after" aria-hidden />
                        ) : null}
                        <button
                          type="button"
                          className="min-w-0 flex-1 text-left"
                          onClick={() =>
                            setSelected({ scope: "kanban", fieldId: f.id })
                          }
                        >
                          <span className="tabular-nums text-[var(--dz-paper-muted)]">{idx + 1}.</span>{" "}
                          <span className="font-mono">{f.name}</span>
                          {f.string ? (
                            <span className="ml-2 text-xs text-[var(--dz-paper-muted)]">
                              {f.string}
                            </span>
                          ) : null}
                        </button>
                        <span className="designer-row-tools flex shrink-0 items-center gap-0.5">
                          <button
                            type="button"
                            className="designer-row-tool"
                            disabled={idx === 0}
                            aria-label={`Move ${f.name} up`}
                            onPointerDown={(e) => e.stopPropagation()}
                            onClick={() => moveKanbanField(f.id, -1)}
                          >
                            <ChevronUp className="h-3.5 w-3.5" aria-hidden />
                          </button>
                          <button
                            type="button"
                            className="designer-row-tool"
                            disabled={idx >= kanbanFields.length - 1}
                            aria-label={`Move ${f.name} down`}
                            onPointerDown={(e) => e.stopPropagation()}
                            onClick={() => moveKanbanField(f.id, 1)}
                          >
                            <ChevronDown className="h-3.5 w-3.5" aria-hidden />
                          </button>
                          <button
                            type="button"
                            className="designer-quiet-btn is-danger"
                            onPointerDown={(e) => e.stopPropagation()}
                            onClick={() => {
                              setKanbanFields((cols) =>
                                cols.filter((c) => c.id !== f.id),
                              );
                              setSelected((sel) =>
                                sel?.scope === "kanban" && sel.fieldId === f.id
                                  ? null
                                  : sel,
                              );
                            }}
                          >
                            Remove
                          </button>
                        </span>
                        <DesignerGrip />
                        {meta.isDragging ? (
                          <DesignerPointerGhost label={f.string || f.name} name={f.name} />
                        ) : null}
                      </>
                    )}
                  </ReorderableBlocks>
                </div>
              </div>
            )}
          </section>
  );
}
