"use client";

import type { Connection, FieldRow } from "@/lib/api";
import {
  connectionSupports,
  connectionUnsupportedReason,
  injectStrategyCapabilityId,
} from "@/lib/capabilities";
import {
  NicheWidgetPalette,
  type NicheWidgetEntry,
} from "@/components/designer/NicheWidgetPalette";

export type DesignerAdvancedFieldsAsideProps = {
  connection: Connection | null;
  viewType: string;
  fields: FieldRow[];
  newFieldName: string;
  setNewFieldName: (v: string) => void;
  newFieldLabel: string;
  setNewFieldLabel: (v: string) => void;
  newFieldType: string;
  setNewFieldType: (v: string) => void;
  injectStrategy: "inherit" | "mutate";
  setInjectStrategy: (v: "inherit" | "mutate") => void;
  confirmPhrase: string;
  setConfirmPhrase: (v: string) => void;
  busy: boolean;
  setDragField: (v: string | null) => void;
  addListColumn: (fieldName: string) => void;
  addSearchField: (fieldName: string) => void;
  addKanbanField: (fieldName: string) => void;
  nicheWidgets: NicheWidgetEntry[];
  colorPalette: Array<{ index: number; name: string }>;
  onCreateAndInject: (opts?: {
    confirm_advanced?: boolean;
    confirm_phrase?: string;
  }) => void | Promise<void>;
  onPickNicheWidget: (w: NicheWidgetEntry) => void;
};

export function DesignerAdvancedFieldsAside({
  connection,
  viewType,
  fields,
  newFieldName,
  setNewFieldName,
  newFieldLabel,
  setNewFieldLabel,
  newFieldType,
  setNewFieldType,
  injectStrategy,
  setInjectStrategy,
  confirmPhrase,
  setConfirmPhrase,
  busy,
  setDragField,
  addListColumn,
  addSearchField,
  addKanbanField,
  nicheWidgets,
  colorPalette,
  onCreateAndInject,
  onPickNicheWidget,
}: DesignerAdvancedFieldsAsideProps) {
  return (
          <aside className="border border-border-subtle bg-surface-muted/70 p-4">
            <p className="text-xs uppercase tracking-wide text-muted">Fields</p>
            <div className="mt-3 space-y-2 border border-border-subtle p-2 text-xs">
              <p className="text-muted">Create field on model</p>
              <input
                value={newFieldName}
                onChange={(e) => setNewFieldName(e.target.value)}
                placeholder="x_my_field"
                className="w-full border border-border-subtle bg-surface px-2 py-1 font-mono"
              />
              <input
                value={newFieldLabel}
                onChange={(e) => setNewFieldLabel(e.target.value)}
                placeholder="Label"
                className="w-full border border-border-subtle bg-surface px-2 py-1"
              />
              <select
                value={newFieldType}
                onChange={(e) => setNewFieldType(e.target.value)}
                className="w-full border border-border-subtle bg-surface px-2 py-1"
              >
                <option value="char">char</option>
                <option value="text">text</option>
                <option value="integer">integer</option>
                <option value="float">float</option>
                <option value="boolean">boolean</option>
                <option value="date">date</option>
                <option value="selection">selection</option>
                <option value="many2one">many2one</option>
                <option value="json">json</option>
              </select>
              <label className="block text-[11px] text-muted">
                Inject strategy
                <select
                  value={injectStrategy}
                  onChange={(e) =>
                    setInjectStrategy(e.target.value as "inherit" | "mutate")
                  }
                  className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1 text-sm text-ink"
                >
                  <option
                    value="inherit"
                    disabled={!connectionSupports(connection, "view_inject_inherit")}
                  >
                    inherit (xpath child)
                    {!connectionSupports(connection, "view_inject_inherit")
                      ? " — unavailable"
                      : ""}
                  </option>
                  <option
                    value="mutate"
                    disabled={!connectionSupports(connection, "view_inject_mutate")}
                    title={
                      connectionUnsupportedReason(connection, "view_inject_mutate") ??
                      undefined
                    }
                  >
                    mutate (overwrite parent)
                    {!connectionSupports(connection, "view_inject_mutate")
                      ? " — unavailable"
                      : ""}
                  </option>
                </select>
              </label>
              {!connectionSupports(
                connection,
                injectStrategyCapabilityId(injectStrategy),
              ) && (
                <p className="text-[11px] text-warning">
                  {connectionUnsupportedReason(
                    connection,
                    injectStrategyCapabilityId(injectStrategy),
                  )}
                </p>
              )}
              {injectStrategy === "mutate" &&
                connectionSupports(connection, "view_inject_mutate") && (
                  <p className="text-[11px] text-warning">
                    Mutate overwrites parent view arch — requires advanced confirm.
                  </p>
                )}
              <input
                value={confirmPhrase}
                onChange={(e) => setConfirmPhrase(e.target.value)}
                placeholder="I understand the risks"
                className="w-full border border-border-subtle bg-surface px-2 py-1"
              />
              <button
                type="button"
                disabled={
                  busy ||
                  !model ||
                  !newFieldName.startsWith("x_") ||
                  !connectionSupports(
                    connection,
                    injectStrategyCapabilityId(injectStrategy),
                  )
                }
                title={
                  connectionUnsupportedReason(
                    connection,
                    injectStrategyCapabilityId(injectStrategy),
                  ) ?? undefined
                }
                className="w-full border border-border-subtle px-2 py-1 text-muted disabled:opacity-40"
                onClick={() => void onCreateAndInject()}
              >
                Create + inject
              </button>
            </div>
            <ul className="mt-3 max-h-[28rem] space-y-1 overflow-auto text-sm" data-testid="designer-field-list-advanced">
              {fields.map((f) => (
                <li
                  key={f.id}
                  draggable={viewType === "form" || viewType === "kanban"}
                  onDragStart={(e) => {
                    setDragField(f.name);
                    e.dataTransfer.setData("text/odoo-field", f.name);
                    e.dataTransfer.effectAllowed = "copy";
                  }}
                  onClick={() => {
                    if (viewType === "list") addListColumn(f.name);
                    if (viewType === "search") addSearchField(f.name);
                    if (viewType === "kanban") addKanbanField(f.name);
                  }}
                  className="cursor-grab border border-transparent px-2 py-1.5 hover:border-border-subtle"
                >
                  <span className="font-mono text-muted">{f.name}</span>
                  <span className="block text-xs text-muted">
                    {f.field_description} · {f.ttype}
                  </span>
                </li>
              ))}
              {fields.length === 0 && (
                <li className="text-muted">Load a model to populate.</li>
              )}
            </ul>
            {(viewType === "form" || viewType === "kanban") && (
              <NicheWidgetPalette
                widgets={nicheWidgets}
                colorPalette={colorPalette}
                onPick={(w) => void onPickNicheWidget(w)}
              />
            )}
          </aside>
  );
}
