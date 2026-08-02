"use client";

import { useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { FieldPalette } from "@/components/designer/FieldPalette";
import { FormCanvas } from "@/components/designer/FormCanvas";
import { KanbanCardPreview } from "@/components/designer/KanbanCardPreview";
import { PropsInspector } from "@/components/designer/PropsInspector";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import type { CapabilityMatrix, Connection } from "@/lib/api";

type ViewMode =
  | "form"
  | "list"
  | "kanban"
  | "calendar"
  | "graph"
  | "pivot"
  | "map"
  | "activity"
  | "gantt"
  | "cohort"
  | "search";

const ODOO_19_CAPS: CapabilityMatrix = {
  major: 19,
  edition: "community",
  server_version: "19.0",
  ga: true,
  message: "Odoo 19 Community — GA",
  supported: [
    "base_automation_safe_triggers",
    "list_as_list_type",
    "list_tree_fallback",
    "object_create_crud_model",
    "object_write_update_path",
    "related_write_dotted_path",
    "smart_button_inherit_box",
    "view_inject_inherit",
    "view_inject_mutate",
  ],
  unsupported: [],
};

const MOCK_CONNECTION: Connection = {
  id: "e2e-mock-19",
  name: "E2E Mock Odoo 19",
  url: "http://127.0.0.1:8069",
  db_name: "odoo_dev",
  username: "admin",
  server_version: "19.0",
  created_at: null,
  updated_at: null,
  capabilities: ODOO_19_CAPS,
};

const SAMPLE_PALETTE = [
  { name: "x_name", ttype: "char", label: "Name" },
  { name: "x_stage", ttype: "selection", label: "Stage" },
  { name: "x_partner_id", ttype: "many2one", label: "Customer" },
  { name: "x_priority", ttype: "selection", label: "Priority" },
  { name: "x_amount", ttype: "float", label: "Amount" },
  { name: "x_notes", ttype: "text", label: "Notes" },
];

const SAMPLE_FORM_GROUPS = [
  {
    id: "g1",
    string: "General",
    fields: [
      { id: "f1", name: "x_name", string: "Name" },
      { id: "f2", name: "x_partner_id", string: "Customer" },
      { id: "f3", name: "x_priority", string: "Priority" },
    ],
  },
  {
    id: "g2",
    string: "Details",
    fields: [
      { id: "f4", name: "x_amount", string: "Amount" },
      { id: "f5", name: "x_notes", string: "Notes" },
    ],
  },
];

const SAMPLE_LIST_COLUMNS = [
  { id: "c1", name: "x_name", string: "Name" },
  { id: "c2", name: "x_stage", string: "Stage" },
  { id: "c3", name: "x_partner_id", string: "Customer" },
  { id: "c4", name: "x_amount", string: "Amount" },
];

const SAMPLE_KANBAN_FIELDS = [
  { id: "k1", name: "x_name", string: "Name" },
  { id: "k2", name: "x_partner_id", string: "Customer" },
  { id: "k3", name: "x_amount", string: "Amount" },
  { id: "k4", name: "x_priority", string: "Priority" },
];

function parseMode(raw: string | null): ViewMode {
  const allowed: ViewMode[] = [
    "form",
    "list",
    "kanban",
    "calendar",
    "graph",
    "pivot",
    "map",
    "activity",
    "gantt",
    "cohort",
    "search",
  ];
  if (raw && (allowed as string[]).includes(raw)) return raw as ViewMode;
  return "form";
}

function DesignerHarnessInner() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const searchParams = useSearchParams();
  const mode = parseMode(searchParams.get("mode"));
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(() =>
    mode === "form" ? "f1" : mode === "list" ? "c2" : "k2",
  );
  const [kanbanFields, setKanbanFields] = useState(SAMPLE_KANBAN_FIELDS);
  const [listColumns, setListColumns] = useState(SAMPLE_LIST_COLUMNS);
  const [formGroups, setFormGroups] = useState(SAMPLE_FORM_GROUPS);

  const title = "Ticket";
  const model = "x_ticket";

  const selectedMeta = useMemo(() => {
    if (mode === "form") {
      for (const g of formGroups) {
        const f = g.fields.find((x) => x.id === selectedFieldId);
        if (f) return f;
      }
    }
    if (mode === "list") return listColumns.find((c) => c.id === selectedFieldId);
    return kanbanFields.find((f) => f.id === selectedFieldId);
  }, [mode, formGroups, listColumns, kanbanFields, selectedFieldId]);

  function moveInList<T extends { id: string }>(
    items: T[],
    id: string,
    dir: -1 | 1,
  ): T[] {
    const idx = items.findIndex((x) => x.id === id);
    if (idx < 0) return items;
    const next = idx + dir;
    if (next < 0 || next >= items.length) return items;
    const copy = [...items];
    const [item] = copy.splice(idx, 1);
    copy.splice(next, 0, item);
    return copy;
  }

  if (!enabled) {
    return <p>E2E harness disabled</p>;
  }

  return (
    <main
      className="odoo-shell min-h-screen px-6 py-10 text-[#f4eef2]"
      data-testid="designer-harness"
      data-mode={mode}
    >
      <div className="mx-auto max-w-7xl">
        <h1 className="font-[family-name:var(--font-display)] text-3xl text-[#faf6f9]">
          View designer
        </h1>
        <p className="mt-1 text-sm text-[#8f7a88]" data-testid="harness-connection">
          {MOCK_CONNECTION.name} · drag fields onto the canvas · saves real{" "}
          <code className="text-[#c9a9c0]">ir.ui.view</code> arch
        </p>
        <VersionAwarenessBanner capabilities={MOCK_CONNECTION.capabilities} />

        <div className="mt-6 flex flex-wrap items-end gap-3">
          <label className="text-sm">
            <span className="text-[#a8909e]">Model</span>
            <input
              readOnly
              value={model}
              className="mt-1 block w-64 border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
              data-testid="harness-model"
            />
          </label>
          <label className="text-sm">
            <span className="text-[#a8909e]">View type</span>
            <select
              value={mode}
              onChange={() => undefined}
              disabled
              className="mt-1 block border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
              data-testid="harness-view-type"
            >
              <option value="form">form</option>
              <option value="list">list</option>
              <option value="kanban">kanban</option>
              <option value="search">search</option>
              <option value="calendar">calendar</option>
              <option value="graph">graph</option>
              <option value="pivot">pivot</option>
              <option value="map">map</option>
              <option value="activity">activity</option>
              <option value="gantt">gantt</option>
              <option value="cohort">cohort</option>
            </select>
          </label>
          {mode === "kanban" && (
            <label className="text-sm">
              <span className="text-[#a8909e]">Group by</span>
              <select
                value="x_stage"
                disabled
                className="mt-1 block border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
                data-testid="harness-groupby"
              >
                <option value="x_stage">x_stage · selection</option>
              </select>
            </label>
          )}
          <label className="text-sm">
            <span className="text-[#a8909e]">Title</span>
            <input
              readOnly
              value={title}
              className="mt-1 block w-48 border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
            />
          </label>
          <button
            type="button"
            className="h-10 bg-[#714B67] px-5 text-sm font-semibold text-white"
          >
            Save to Odoo
          </button>
          <a
            href="#"
            className="inline-flex h-10 items-center border border-[#c9a9c0] px-4 text-sm text-[#c9a9c0]"
          >
            Open in Odoo
          </a>
        </div>

        {mode === "form" && (
          <div
            className="mt-6 grid gap-4 lg:grid-cols-[200px_1fr_240px]"
            data-testid="designer-form-layout"
          >
            <FieldPalette fields={SAMPLE_PALETTE} />
            <div>
              <h2 className="mb-2 text-sm font-semibold text-[var(--odoo-primary-light)]">
                Odoo-style canvas
              </h2>
              <FormCanvas
                title={title}
                statusbar="x_stage"
                headerButtons={["Confirm", "Cancel"]}
                smartButtons={[
                  { id: "sb1", string: "Orders" },
                  { id: "sb2", string: "Invoices" },
                ]}
                groups={formGroups}
                selectedFieldId={selectedFieldId}
                onSelectField={setSelectedFieldId}
                onMoveField={(fieldId, dir) => {
                  setFormGroups((groups) =>
                    groups.map((g) => ({
                      ...g,
                      fields: moveInList(g.fields, fieldId, dir),
                    })),
                  );
                }}
              />
            </div>
            <PropsInspector title="Field properties">
              {selectedMeta ? (
                <div className="space-y-3 text-sm text-[#1a1a1a]">
                  <p className="font-mono text-[var(--odoo-primary)]">{selectedMeta.name}</p>
                  <label className="flex items-center gap-2">
                    <input type="checkbox" defaultChecked={false} readOnly />
                    <span>Required</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input type="checkbox" defaultChecked={false} readOnly />
                    <span>Readonly</span>
                  </label>
                  <label className="block text-xs">
                    Widget
                    <input
                      defaultValue=""
                      readOnly
                      className="mt-1 w-full border border-[var(--odoo-border)] px-2 py-1 font-mono text-xs"
                    />
                  </label>
                </div>
              ) : (
                <p className="text-xs text-[var(--odoo-muted)]">
                  Select a field on the canvas, or drag from the palette.
                </p>
              )}
            </PropsInspector>
          </div>
        )}

        {mode === "list" && (
          <div
            className="mt-6 grid gap-4 lg:grid-cols-[200px_1fr_240px]"
            data-testid="designer-list-layout"
          >
            <FieldPalette fields={SAMPLE_PALETTE} />
            <div>
              <h2 className="mb-2 text-sm font-semibold text-[var(--odoo-primary-light)]">
                List columns
              </h2>
              <div className="odoo-form-canvas overflow-hidden shadow-sm">
                <div className="odoo-form-header flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold text-[var(--odoo-primary)]">
                    {title}
                  </span>
                  <span className="rounded border border-[var(--odoo-border)] bg-white px-2 py-0.5 text-xs">
                    list
                  </span>
                </div>
                <div className="space-y-3 p-3">
                  <div className="grid gap-2 sm:grid-cols-3">
                    <label className="block text-xs text-[var(--odoo-muted)]">
                      decoration-danger
                      <input
                        readOnly
                        value="x_priority == 'urgent'"
                        className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1 font-mono text-xs text-[var(--odoo-sheet-fg)]"
                      />
                    </label>
                    <label className="block text-xs text-[var(--odoo-muted)]">
                      decoration-info
                      <input
                        readOnly
                        value="x_stage == 'new'"
                        className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1 font-mono text-xs text-[var(--odoo-sheet-fg)]"
                      />
                    </label>
                    <label className="block text-xs text-[var(--odoo-muted)]">
                      decoration-muted
                      <input
                        readOnly
                        value="x_amount == 0"
                        className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1 font-mono text-xs text-[var(--odoo-sheet-fg)]"
                      />
                    </label>
                  </div>
                  <div className="overflow-x-auto border border-[var(--odoo-border)] bg-white">
                    <table className="w-full text-left text-sm" data-testid="list-preview-table">
                      <thead className="bg-[#f0eeeb] text-xs uppercase text-[var(--odoo-muted)]">
                        <tr>
                          {listColumns.map((c) => (
                            <th key={c.id} className="border-b border-[var(--odoo-border)] px-3 py-2">
                              {c.string || c.name}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        <tr className="text-[var(--odoo-sheet-fg)]">
                          <td className="border-b border-[var(--odoo-border)] px-3 py-2">
                            Sample ticket
                          </td>
                          <td className="border-b border-[var(--odoo-border)] px-3 py-2">New</td>
                          <td className="border-b border-[var(--odoo-border)] px-3 py-2">
                            Acme Corp
                          </td>
                          <td className="border-b border-[var(--odoo-border)] px-3 py-2">
                            120.00
                          </td>
                        </tr>
                        <tr className="bg-[#f5eef3]/40 text-[var(--odoo-sheet-fg)]">
                          <td className="px-3 py-2">Urgent follow-up</td>
                          <td className="px-3 py-2">In progress</td>
                          <td className="px-3 py-2">Beta LLC</td>
                          <td className="px-3 py-2">0.00</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <ul className="space-y-1">
                    {listColumns.map((f, idx) => (
                      <li
                        key={f.id}
                        className={`flex items-center justify-between border px-2 py-1.5 text-sm ${
                          selectedFieldId === f.id
                            ? "border-[var(--odoo-primary)] bg-[#f5eef3]"
                            : "border-[var(--odoo-border)] bg-white"
                        }`}
                      >
                        <button
                          type="button"
                          className="flex-1 text-left font-mono text-xs"
                          onClick={() => setSelectedFieldId(f.id)}
                        >
                          {idx + 1}. {f.string || f.name}{" "}
                          <span className="text-[var(--odoo-muted)]">{f.name}</span>
                        </button>
                        <span className="flex gap-1">
                          <button
                            type="button"
                            className="text-xs text-[var(--odoo-primary)] disabled:opacity-30"
                            disabled={idx === 0}
                            aria-label={`Move ${f.name} up`}
                            onClick={() =>
                              setListColumns((cols) => moveInList(cols, f.id, -1))
                            }
                          >
                            ↑
                          </button>
                          <button
                            type="button"
                            className="text-xs text-[var(--odoo-primary)] disabled:opacity-30"
                            disabled={idx >= listColumns.length - 1}
                            aria-label={`Move ${f.name} down`}
                            onClick={() =>
                              setListColumns((cols) => moveInList(cols, f.id, 1))
                            }
                          >
                            ↓
                          </button>
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
            <PropsInspector title="Column properties">
              {selectedMeta ? (
                <div className="space-y-3 text-sm text-[#1a1a1a]">
                  <p className="font-mono text-[var(--odoo-primary)]">{selectedMeta.name}</p>
                  <p className="text-xs text-[var(--odoo-muted)]">
                    {selectedMeta.string || "No label"}
                  </p>
                </div>
              ) : (
                <p className="text-xs text-[var(--odoo-muted)]">
                  Select a list column to inspect.
                </p>
              )}
            </PropsInspector>
          </div>
        )}

        {mode === "kanban" && (
          <div
            className="mt-6 grid gap-4 lg:grid-cols-[200px_1fr_240px]"
            data-testid="designer-kanban-layout"
          >
            <FieldPalette fields={SAMPLE_PALETTE} />
            <div>
              <h2 className="mb-2 text-sm font-semibold text-[var(--odoo-primary-light)]">
                Kanban card preview
              </h2>
              <KanbanCardPreview
                title={title}
                groupBy="x_stage"
                fields={kanbanFields}
                selectedFieldId={selectedFieldId}
                onSelectField={setSelectedFieldId}
                onMoveField={(fieldId, dir) => {
                  setKanbanFields((fields) => moveInList(fields, fieldId, dir));
                }}
                onRemoveField={(fieldId) => {
                  setKanbanFields((fields) => fields.filter((f) => f.id !== fieldId));
                  setSelectedFieldId((sel) => (sel === fieldId ? null : sel));
                }}
              />
            </div>
            <PropsInspector title="Card field">
              {selectedMeta ? (
                <div className="space-y-3 text-sm text-[#1a1a1a]">
                  <p className="font-mono text-[var(--odoo-primary)]">{selectedMeta.name}</p>
                  <p className="text-xs text-[var(--odoo-muted)]">
                    {selectedMeta.string || "No label from field metadata"}
                  </p>
                  <p className="text-[11px] text-[var(--odoo-muted)]">
                    Card label show/hide (nolabel) is not in our kanban arch helpers yet —
                    values render in order only.
                  </p>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      className="text-xs text-[var(--odoo-primary)]"
                      onClick={() =>
                        setKanbanFields((fields) =>
                          moveInList(fields, selectedMeta.id, -1),
                        )
                      }
                    >
                      Move up
                    </button>
                    <button
                      type="button"
                      className="text-xs text-[var(--odoo-primary)]"
                      onClick={() =>
                        setKanbanFields((fields) =>
                          moveInList(fields, selectedMeta.id, 1),
                        )
                      }
                    >
                      Move down
                    </button>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-[var(--odoo-muted)]">
                  Select a card field, or drop from the palette. Set group-by above.
                </p>
              )}
            </PropsInspector>
          </div>
        )}
      </div>
    </main>
  );
}

export default function E2EDesignerHarnessPage() {
  return (
    <Suspense fallback={<p className="p-8">Loading designer harness…</p>}>
      <DesignerHarnessInner />
    </Suspense>
  );
}
