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

/** Middle column of Advanced layout — form/list/search/kanban structure editors. */
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
  return (
          <section className="border border-border-subtle bg-surface-muted/50 p-4" data-testid="designer-structure-editor">
            <div className="mb-3">
              <h2 className="text-sm font-semibold text-accent">
                {viewType === "form" ? "Form layout (primary)" : "Layout editor"}
              </h2>
              {viewType === "form" && (
                <p className="mt-1 text-xs text-muted">
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
                    className={`border px-3 py-1 text-xs ${
                      toolbarFlash === "group"
                        ? "border-border-subtle bg-surface-muted text-ink"
                        : "border-border-subtle text-muted"
                    }`}
                  >
                    {toolbarFlash === "group" ? "✓ Group added" : "+ Group"}
                  </button>
                  <button
                    type="button"
                    onClick={addNotebook}
                    className={`border px-3 py-1 text-xs ${
                      toolbarFlash === "notebook"
                        ? "border-border-subtle bg-surface-muted text-ink"
                        : "border-border-subtle text-muted"
                    }`}
                  >
                    {toolbarFlash === "notebook" ? "✓ Notebook added" : "+ Notebook"}
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
                    className={`border px-3 py-1 text-xs disabled:opacity-40 ${
                      toolbarFlash === "header"
                        ? "border-border-subtle bg-surface-muted text-ink"
                        : "border-border-subtle text-muted"
                    }`}
                  >
                    {toolbarFlash === "header" ? "✓ Header binder" : "+ Header button"}
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
                    className={`border px-3 py-1 text-xs disabled:opacity-40 ${
                      toolbarFlash === "smart"
                        ? "border-border-subtle bg-surface-muted text-ink"
                        : "border-border-subtle text-muted"
                    }`}
                  >
                    {toolbarFlash === "smart" ? "✓ Smart binder" : "+ Smart button"}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      addButtonToFirstGroup();
                      announceAction("Opening inline button binder…", null, "inline");
                    }}
                    className={`border px-3 py-1 text-xs ${
                      toolbarFlash === "inline"
                        ? "border-border-subtle bg-surface-muted text-ink"
                        : "border-border-subtle text-muted"
                    }`}
                  >
                    {toolbarFlash === "inline" ? "✓ Inline binder" : "+ Inline button"}
                  </button>
                </>
              )}
            </div>

            {viewType === "form" && (
              <div className="mb-4 space-y-3">
                <div className="flex flex-wrap gap-4 border border-dashed border-border-subtle p-3 text-sm text-muted">
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
                <div className="grid gap-3 border border-dashed border-border-subtle p-3 sm:grid-cols-2">
                  <label className="text-xs text-muted">
                    Statusbar field (selection)
                    <select
                      value={statusbarField}
                      onChange={(e) => setStatusbarField(e.target.value)}
                      className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1.5 font-mono text-sm"
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
                  <label className="text-xs text-muted">
                    statusbar_visible (comma-separated)
                    <input
                      value={statusbarVisible}
                      onChange={(e) => setStatusbarVisible(e.target.value)}
                      placeholder="draft,confirmed,done"
                      disabled={!statusbarField}
                      className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1.5 font-mono text-sm disabled:opacity-40"
                    />
                  </label>
                </div>
                <div className="min-h-12 border border-dashed border-border-subtle p-3">
                  <p className="mb-2 text-xs uppercase text-muted">Header buttons</p>
                  <ul className="space-y-1">
                    {headerButtons.map((b) => (
                      <li
                        key={b.id}
                        className="flex items-center justify-between bg-surface px-2 py-1.5 text-sm"
                      >
                        <span className="text-ink">
                          {b.string}{" "}
                          <span className="font-mono text-xs text-muted">
                            type={b.type || "action"} name={b.name || "?"}
                          </span>
                        </span>
                        <button
                          type="button"
                          className="text-xs text-danger"
                          onClick={() =>
                            setHeaderButtons((all) => all.filter((x) => x.id !== b.id))
                          }
                        >
                          remove
                        </button>
                      </li>
                    ))}
                    {headerButtons.length === 0 && (
                      <li className="text-xs text-muted">
                        Bound to real ir.actions.* via type=&quot;action&quot;.
                      </li>
                    )}
                  </ul>
                </div>
                <div className="min-h-12 border border-dashed border-border-subtle p-3">
                  <p className="mb-2 text-xs uppercase text-muted">Smart button box</p>
                  <ul className="space-y-1">
                    {buttonBox.map((b) => (
                      <li
                        key={b.id}
                        className="flex items-center justify-between bg-surface px-2 py-1.5 text-sm"
                      >
                        <span className="text-ink">
                          {b.string}{" "}
                          <span className="font-mono text-xs text-muted">
                            {b.icon || "fa-list"} · action {b.name || "?"}
                            {b.count_field ? ` · count ${b.count_field}` : ""}
                          </span>
                        </span>
                        <button
                          type="button"
                          className="text-xs text-danger"
                          onClick={() => setButtonBox((all) => all.filter((x) => x.id !== b.id))}
                        >
                          remove
                        </button>
                      </li>
                    ))}
                    {buttonBox.length === 0 && (
                      <li className="text-xs text-muted">
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
                      className={`mb-4 min-h-24 border border-dashed border-border-subtle p-3 ${
                        canvasFlashId === child.id ? "ring-2 ring-accent" : ""
                      }`}
                    >
                      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                        <label className="flex min-w-0 flex-1 items-center gap-2 text-xs uppercase text-muted">
                          Group
                          <input
                            value={child.string || ""}
                            onChange={(e) => renameGroup(child.id, e.target.value)}
                            className="min-w-0 flex-1 border border-border-subtle bg-surface px-2 py-1 font-sans text-sm normal-case text-muted"
                            placeholder="untitled"
                          />
                        </label>
                        <button
                          type="button"
                          className="shrink-0 text-xs text-danger"
                          onClick={() => removeFormChild(child.id)}
                        >
                          remove group
                        </button>
                      </div>
                      <ul className="space-y-1">
                        {child.children.map((f) => (
                          <li
                            key={f.id}
                            className={`flex items-center justify-between bg-surface px-2 py-1.5 text-sm ${
                              selected?.fieldId === f.id ? "ring-1 ring-accent" : ""
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
                                <span className="text-ink">
                                  Btn · {f.string}{" "}
                                  <span className="font-mono text-xs text-muted">
                                    {f.type || "action"}:{f.name || "?"}
                                  </span>
                                </span>
                              ) : (
                                <>
                                  <span className="font-mono text-muted">{f.name}</span>
                                  {f.string ? ` — ${f.string}` : ""}
                                </>
                              )}
                            </button>
                            <button
                              type="button"
                              className="text-xs text-danger"
                              onClick={() => removeFormField("group", child.id, f.id)}
                            >
                              remove
                            </button>
                          </li>
                        ))}
                        {child.children.length === 0 && (
                          <li className="text-xs text-muted">Drop fields here</li>
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
                    className={`mb-4 border border-border-subtle p-3 ${
                      canvasFlashId === child.id ? "ring-2 ring-accent" : ""
                    }`}
                  >
                    <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                      <p className="text-xs uppercase text-muted">Notebook</p>
                      <div className="flex gap-3">
                        <button
                          type="button"
                          className="text-xs text-muted"
                          onClick={() => addPageToNotebook(child.id)}
                        >
                          + Page
                        </button>
                        <button
                          type="button"
                          className="text-xs text-danger"
                          onClick={() => removeFormChild(child.id)}
                        >
                          remove notebook
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
                        className={`mb-3 min-h-20 border border-dashed border-border-subtle p-3 ${
                          canvasFlashId === page.id ? "ring-2 ring-accent" : ""
                        }`}
                      >
                        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                          <label className="flex min-w-0 flex-1 items-center gap-2 text-sm text-muted">
                            Page
                            <input
                              value={page.string}
                              onChange={(e) =>
                                renameNotebookPage(child.id, page.id, e.target.value)
                              }
                              className="min-w-0 flex-1 border border-border-subtle bg-surface px-2 py-1 font-mono text-sm"
                              placeholder="Tab title"
                            />
                          </label>
                          <button
                            type="button"
                            className="shrink-0 text-xs text-danger"
                            onClick={() => removeNotebookPage(child.id, page.id)}
                          >
                            remove page
                          </button>
                        </div>
                        <ul className="space-y-1">
                          {page.children.map((f) => (
                            <li
                              key={f.id}
                              className={`flex items-center justify-between bg-surface px-2 py-1.5 text-sm ${
                                selected?.fieldId === f.id ? "ring-1 ring-accent" : ""
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
                                  <span className="text-ink">Btn · {f.string}</span>
                                ) : (
                                  <>
                                    <span className="text-muted">
                                      {resolveFieldLabel(f.name, f.string, fields) || f.name}
                                    </span>
                                    <span className="ml-2 font-mono text-xs text-muted">
                                      {f.name}
                                    </span>
                                  </>
                                )}
                              </button>
                              <button
                                type="button"
                                className="text-xs text-danger"
                                onClick={() =>
                                  removeFormField("page", page.id, f.id, child.id)
                                }
                              >
                                remove
                              </button>
                            </li>
                          ))}
                          {page.children.length === 0 && (
                            <li className="text-xs text-muted">Drop fields here</li>
                          )}
                        </ul>
                      </div>
                    ))}
                  </div>
                );
              })}

            {viewType === "list" && (
              <div className="min-h-40 border border-dashed border-border-subtle p-3">
                <div className="mb-3 flex flex-wrap gap-4 text-sm text-muted">
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
                <label className="mb-3 block text-xs text-muted">
                  default_order (Sort By)
                  <input
                    value={listDefaultOrder}
                    onChange={(e) => setListDefaultOrder(e.target.value)}
                    placeholder="name asc, id desc"
                    className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1 font-mono"
                  />
                </label>
                <div className="mb-3 grid gap-2 sm:grid-cols-3">
                  <label className="block text-xs text-muted">
                    decoration-danger
                    <input
                      value={listDecorationDanger}
                      onChange={(e) => setListDecorationDanger(e.target.value)}
                      placeholder="not x_returned"
                      className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1 font-mono"
                    />
                  </label>
                  <label className="block text-xs text-muted">
                    decoration-info
                    <input
                      value={listDecorationInfo}
                      onChange={(e) => setListDecorationInfo(e.target.value)}
                      placeholder="x_priority == 'high'"
                      className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1 font-mono"
                    />
                  </label>
                  <label className="block text-xs text-muted">
                    decoration-muted
                    <input
                      value={listDecorationMuted}
                      onChange={(e) => setListDecorationMuted(e.target.value)}
                      placeholder="x_active == False"
                      className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1 font-mono"
                    />
                  </label>
                </div>
                <p className="mb-2 text-xs uppercase text-muted">
                  List columns (click a field to add)
                </p>
                <ul className="space-y-1">
                  {listColumns.map((f, idx) => (
                    <li
                      key={f.id}
                      className={`flex items-center justify-between bg-surface px-2 py-1.5 text-sm ${
                        selected?.fieldId === f.id ? "ring-1 ring-accent" : ""
                      }`}
                    >
                      <button
                        type="button"
                        className="text-left"
                        onClick={() => setSelected({ scope: "list", fieldId: f.id })}
                      >
                        {idx + 1}.{" "}
                        <span className="font-mono text-muted">{f.name}</span>
                      </button>
                      <button
                        type="button"
                        className="text-xs text-danger"
                        onClick={() => {
                          setListColumns((cols) => cols.filter((c) => c.id !== f.id));
                          setSelected((sel) => (sel?.fieldId === f.id ? null : sel));
                        }}
                      >
                        remove
                      </button>
                    </li>
                  ))}
                </ul>
                {listColumns.length > 0 ? (
                  <details className="mt-4 rounded border border-border-subtle bg-surface-muted/30 p-3" data-testid="designer-list-preview">
                    <summary className="cursor-pointer text-sm font-semibold text-accent">
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
              <div className="min-h-40 border border-dashed border-border-subtle p-3">
                <p className="mb-2 text-xs uppercase text-muted">
                  Search fields (click a field to add)
                </p>
                <button
                  type="button"
                  className="mb-2 text-xs text-muted"
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
                  + Add search filter
                </button>
                {searchFilters.length > 0 && (
                  <ul className="mb-3 space-y-3 text-xs text-muted">
                    {searchFilters.map((f) => (
                      <li key={f.id} className="border border-border-subtle p-2">
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
                            className="min-w-[8rem] flex-1 border border-border-subtle bg-surface px-2 py-1"
                          />
                          <button
                            type="button"
                            className="text-muted"
                            onClick={() =>
                              setEditingFilterId((id) => (id === f.id ? null : f.id))
                            }
                          >
                            {editingFilterId === f.id ? "Hide domain" : "Edit domain"}
                          </button>
                          <button
                            type="button"
                            className="text-danger"
                            onClick={() =>
                              setSearchFilters((all) => all.filter((x) => x.id !== f.id))
                            }
                          >
                            remove
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
                          <span className="font-mono text-muted">{f.domain || "[]"}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
                <div className="mb-3 border border-border-subtle p-2">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <p className="text-xs uppercase text-muted">Group-by filters</p>
                    <button
                      type="button"
                      className="text-xs text-muted"
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
                      + Add group-by filter
                    </button>
                  </div>
                  {searchGroupByFilters.length === 0 ? (
                    <p className="text-xs text-muted">
                      No group-by filters. Context example:{" "}
                      <code className="text-muted">{"{'group_by': 'x_stage'}"}</code>
                    </p>
                  ) : (
                    <ul className="space-y-2 text-xs text-muted">
                      {searchGroupByFilters.map((f) => (
                        <li key={f.id} className="grid gap-2 border border-border-subtle p-2 sm:grid-cols-3">
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
                              className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1 font-mono"
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
                              className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1"
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
                              className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1 font-mono"
                            />
                          </label>
                          <button
                            type="button"
                            className="justify-self-start text-danger sm:col-span-3"
                            onClick={() =>
                              setSearchGroupByFilters((all) =>
                                all.filter((x) => x.id !== f.id),
                              )
                            }
                          >
                            remove
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <ul className="space-y-1">
                  {searchFields.map((f, idx) => (
                    <li
                      key={f.id}
                      className={`flex items-center justify-between bg-surface px-2 py-1.5 text-sm ${
                        selected?.fieldId === f.id ? "ring-1 ring-accent" : ""
                      }`}
                    >
                      <button
                        type="button"
                        className="text-left"
                        onClick={() => setSelected({ scope: "search", fieldId: f.id })}
                      >
                        {idx + 1}.{" "}
                        <span className="font-mono text-muted">{f.name}</span>
                      </button>
                      <button
                        type="button"
                        className="text-xs text-danger"
                        onClick={() => {
                          setSearchFields((cols) => cols.filter((c) => c.id !== f.id));
                          setSelected((sel) => (sel?.fieldId === f.id ? null : sel));
                        }}
                      >
                        remove
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {viewType === "kanban" && (
              <div className="min-h-40 space-y-3">
                <div className="flex flex-wrap gap-4 border border-dashed border-border-subtle p-3 text-sm text-muted">
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
                <div className="border border-border-subtle bg-surface p-3">
                  <p className="mb-2 text-xs uppercase tracking-wide text-muted">
                    Card field order
                    {kanbanGroupBy ? (
                      <span className="ml-2 rounded bg-accent px-1.5 py-0.5 text-[10px] normal-case text-white">
                        group by {kanbanGroupBy}
                      </span>
                    ) : null}
                  </p>
                  <ul className="space-y-1">
                    {kanbanFields.map((f, idx) => (
                      <li
                        key={f.id}
                        className={`flex items-center justify-between gap-2 px-2 py-1.5 text-sm ${
                          selected?.scope === "kanban" && selected.fieldId === f.id
                            ? "bg-surface-muted ring-1 ring-accent"
                            : "bg-surface"
                        }`}
                      >
                        <button
                          type="button"
                          className="min-w-0 flex-1 text-left"
                          onClick={() =>
                            setSelected({ scope: "kanban", fieldId: f.id })
                          }
                        >
                          <span className="text-muted">{idx + 1}.</span>{" "}
                          <span className="font-mono text-muted">{f.name}</span>
                          {f.string ? (
                            <span className="ml-2 text-xs text-muted">
                              {f.string}
                            </span>
                          ) : null}
                        </button>
                        <span className="flex shrink-0 items-center gap-2">
                          <button
                            type="button"
                            className="text-xs text-muted disabled:opacity-30"
                            disabled={idx === 0}
                            aria-label={`Move ${f.name} up`}
                            onClick={() => moveKanbanField(f.id, -1)}
                          >
                            ↑
                          </button>
                          <button
                            type="button"
                            className="text-xs text-muted disabled:opacity-30"
                            disabled={idx >= kanbanFields.length - 1}
                            aria-label={`Move ${f.name} down`}
                            onClick={() => moveKanbanField(f.id, 1)}
                          >
                            ↓
                          </button>
                          <button
                            type="button"
                            className="text-xs text-danger"
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
                            remove
                          </button>
                        </span>
                      </li>
                    ))}
                    {kanbanFields.length === 0 && (
                      <li className="text-xs text-muted">
                        Click or drop fields from the palette to build the card.
                      </li>
                    )}
                  </ul>
                </div>
              </div>
            )}
          </section>
  );
}
