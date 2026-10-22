"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { DesignerAdvancedStructureCanvas } from "@/components/designer/DesignerAdvancedStructureCanvas";
import type {
  DesignerButton,
  DesignerField,
  FormChild,
  SearchFilter,
  SearchGroupByFilter,
  SelectedField,
  ViewType,
} from "@/components/designer/designer-model";
import { moveIndexById } from "@/components/ui/canvas/ReorderableBlocks";
import type { Connection, FieldRow } from "@/lib/api";

/**
 * UI-S-12 harness for the second structure canvas (Advanced layout).
 * `?view=form|list|kanban|search`. Mock data only, no API calls.
 */

const CONNECTION: Connection = {
  id: "e2e-mock-19",
  name: "E2E Mock Odoo 19",
  url: "http://127.0.0.1:8069",
  db_name: "odoo_dev",
  username: "admin",
  server_version: "19.0",
  write_mode: "standard",
  created_at: null,
  updated_at: null,
  capabilities: {
    major: 19,
    edition: "community",
    server_version: "19.0",
    ga: true,
    message: "Odoo 19 Community",
    supported: ["object_write_update_path", "smart_button_inherit_box", "view_inject_inherit"],
    unsupported: [],
  },
};

function row(id: number, name: string, label: string, ttype: string): FieldRow {
  return {
    id,
    name,
    field_description: label,
    ttype,
    required: false,
    readonly: false,
    relation: null,
    state: "manual",
  };
}

const FIELDS: FieldRow[] = [
  row(1, "x_name", "Name", "char"),
  row(2, "x_stage", "Stage", "selection"),
  row(3, "x_partner_id", "Customer", "many2one"),
  row(4, "x_priority", "Priority", "selection"),
  row(5, "x_amount", "Amount", "float"),
  row(6, "x_notes", "Notes", "text"),
];

function f(id: string, name: string, string?: string): DesignerField {
  return { kind: "field", id, name, string };
}

const FORM_CHILDREN: FormChild[] = [
  {
    kind: "group",
    id: "g1",
    string: "General",
    children: [
      f("f1", "x_name"),
      f("f2", "x_partner_id"),
      { kind: "button", id: "b1", string: "Assign to me", name: "action_assign", type: "object" },
    ],
  },
  { kind: "group", id: "g2", string: "Details", children: [f("f4", "x_amount"), f("f5", "x_notes")] },
  {
    kind: "notebook",
    id: "nb1",
    pages: [{ id: "pg1", string: "Lines", children: [f("f6", "x_priority")] }],
  },
];

const HEADER_BUTTONS: DesignerButton[] = [
  { kind: "button", id: "h1", string: "Confirm", name: "action_confirm", type: "object" },
];

const SMART_BUTTONS: DesignerButton[] = [
  { kind: "button", id: "s1", string: "Orders", name: "action_view_orders", icon: "fa-list", count_field: "x_order_count" },
];

function parseView(raw: string | null): ViewType {
  return raw === "list" || raw === "kanban" || raw === "search" ? raw : "form";
}

const noop = () => undefined;

function StructureHarnessInner() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const viewType = parseView(useSearchParams().get("view"));
  const [formChildren, setFormChildren] = useState<FormChild[]>(FORM_CHILDREN);
  const [headerButtons, setHeaderButtons] = useState<DesignerButton[]>(HEADER_BUTTONS);
  const [buttonBox, setButtonBox] = useState<DesignerButton[]>(SMART_BUTTONS);
  const [listColumns, setListColumns] = useState<DesignerField[]>([
    f("c1", "x_name"),
    f("c2", "x_stage"),
    f("c3", "x_partner_id"),
    f("c4", "x_amount"),
  ]);
  const [searchFields, setSearchFields] = useState<DesignerField[]>([f("s1", "x_name"), f("s2", "x_partner_id")]);
  const [searchFilters, setSearchFilters] = useState<SearchFilter[]>([
    { id: "sf1", name: "filter_urgent", string: "Urgent", domain: "[('x_priority', '=', 'urgent')]" },
  ]);
  const [searchGroupBy, setSearchGroupBy] = useState<SearchGroupByFilter[]>([]);
  const [editingFilterId, setEditingFilterId] = useState<string | null>(null);
  const [kanbanFields, setKanbanFields] = useState<DesignerField[]>([
    f("k1", "x_name", "Name"),
    f("k2", "x_partner_id", "Customer"),
    f("k3", "x_amount", "Amount"),
  ]);
  const [selected, setSelected] = useState<SelectedField | null>(
    viewType === "kanban" ? { scope: "kanban", fieldId: "k2" } : { scope: "form-group", groupId: "g1", fieldId: "f2" },
  );
  const [flags, setFlags] = useState({ create: true, edit: true, del: true, dup: true, multi: false, sample: false, quick: true });
  const [dangerDeco, setDangerDeco] = useState("x_priority == 'urgent'");
  const [infoDeco, setInfoDeco] = useState("x_stage == 'new'");
  const [mutedDeco, setMutedDeco] = useState("");
  const [defaultOrder, setDefaultOrder] = useState("x_priority desc, id desc");
  const [statusbarField, setStatusbarField] = useState("x_stage");
  const [statusbarVisible, setStatusbarVisible] = useState("new,in_progress,done");

  if (!enabled) return <p className="p-8">E2E harness disabled</p>;

  const set = (k: keyof typeof flags) => (v: boolean) => setFlags((x) => ({ ...x, [k]: v }));

  return (
    <main className="min-h-screen bg-background text-ink" data-testid="designer-structure-harness" data-view={viewType}>
      <div className="designer-studio-shell min-h-screen">
        <div className="designer-studio-canvas min-h-screen">
          <div className="mx-auto max-w-[56rem]">
            <DesignerAdvancedStructureCanvas
              viewType={viewType}
              connection={CONNECTION}
              model="x_ticket"
              title="Ticket"
              toolbarFlash={null}
              canvasFlashId={null}
              previewTheme={null}
              viewSample={flags.sample}
              setViewSample={set("sample")}
              formChildren={formChildren}
              headerButtons={headerButtons}
              buttonBox={buttonBox}
              setHeaderButtons={setHeaderButtons}
              setButtonBox={setButtonBox}
              statusbarField={statusbarField}
              setStatusbarField={setStatusbarField}
              statusbarVisible={statusbarVisible}
              setStatusbarVisible={setStatusbarVisible}
              formCanCreate={flags.create}
              formCanEdit={flags.edit}
              formCanDelete={flags.del}
              formCanDuplicate={flags.dup}
              setFormCanCreate={set("create")}
              setFormCanEdit={set("edit")}
              setFormCanDelete={set("del")}
              setFormCanDuplicate={set("dup")}
              listColumns={listColumns}
              setListColumns={setListColumns}
              listDecorationDanger={dangerDeco}
              listDecorationInfo={infoDeco}
              listDecorationMuted={mutedDeco}
              setListDecorationDanger={setDangerDeco}
              setListDecorationInfo={setInfoDeco}
              setListDecorationMuted={setMutedDeco}
              listCanCreate={flags.create}
              listCanEdit={flags.edit}
              listCanDelete={flags.del}
              listMultiEdit={flags.multi}
              listDefaultOrder={defaultOrder}
              setListCanCreate={set("create")}
              setListCanEdit={set("edit")}
              setListCanDelete={set("del")}
              setListMultiEdit={set("multi")}
              setListDefaultOrder={setDefaultOrder}
              searchFields={searchFields}
              setSearchFields={setSearchFields}
              searchFilters={searchFilters}
              setSearchFilters={setSearchFilters}
              searchGroupByFilters={searchGroupBy}
              setSearchGroupByFilters={setSearchGroupBy}
              editingFilterId={editingFilterId}
              setEditingFilterId={setEditingFilterId}
              kanbanFields={kanbanFields}
              setKanbanFields={setKanbanFields}
              kanbanGroupBy="x_stage"
              kanbanCanCreate={flags.create}
              kanbanQuickCreate={flags.quick}
              setKanbanCanCreate={set("create")}
              setKanbanQuickCreate={set("quick")}
              moveKanbanField={(id, dir) => setKanbanFields((all) => moveIndexById(all, id, dir))}
              addKanbanField={noop}
              fields={FIELDS}
              selected={selected}
              setSelected={setSelected}
              addGroup={noop}
              addNotebook={noop}
              addButtonToFirstGroup={noop}
              openBindDialog={noop}
              dropOnGroup={noop}
              dropOnPage={noop}
              removeFormChild={(id) => setFormChildren((all) => all.filter((c) => c.id !== id))}
              removeNotebookPage={noop}
              renameNotebookPage={noop}
              renameGroup={(id, string) =>
                setFormChildren((all) => all.map((c) => (c.id === id && c.kind === "group" ? { ...c, string } : c)))
              }
              addPageToNotebook={noop}
              removeFormField={noop}
              announceAction={noop}
            />
          </div>
        </div>
      </div>
    </main>
  );
}

export default function DesignerStructureHarnessPage() {
  return (
    <Suspense fallback={<p className="p-8">Loading structure harness…</p>}>
      <StructureHarnessInner />
    </Suspense>
  );
}
