import type { EngineNode, EngineRecord } from "@/lib/api/view-engine";
import type { PreviewField, PreviewFormView } from "@/lib/draft-form-preview";

/** Draft mode (SPEC stage 4): an App Studio / Draft Studio design that isn't in Odoo yet, shown by the
 * shared engine canvas. Nothing here is real data: values are samples and are labelled as such. */
const node = (id: string, tag: string, kind: string, label: string, children: EngineNode[] = [], extra: Partial<EngineNode> = {}): EngineNode => ({
  id, tag, kind, name: null, label, attrs: {}, anchor: null, locked_reason: "Not in Odoo yet: this is a draft.", children, ...extra,
});

function fieldNode(f: PreviewField): EngineNode {
  return node(`draft:field:${f.id}`, "field", "field", f.string || f.name, [], {
    name: f.name, field_type: f.ttype ?? null, relation: f.relation ?? null, known_field: true,
    attrs: { ...(f.widget ? { widget: f.widget } : {}), ...(f.required ? { required: "1" } : {}) },
  });
}

export function sampleValue(f: PreviewField): unknown {
  const label = f.string || f.name;
  switch (f.ttype) {
    case "boolean": return false;
    case "integer": case "float": case "monetary": return 1;
    case "date": return "2026-01-31";
    case "datetime": return "2026-01-31 09:00";
    case "selection": return f.selection?.[0]?.label ?? "";
    case "one2many": case "many2many": case "binary": case "html": return "";
    default: return `Sample ${label.toLowerCase()}`;
  }
}

export function draftToEngine(view: PreviewFormView): { tree: EngineNode; record: EngineRecord } {
  const record: EngineRecord = { id: 0, display_name: view.title || "New" };
  const take = (fs: PreviewField[]) => fs.map((f) => {
    record[f.name] = sampleValue(f);
    return fieldNode(f);
  });
  const sheet: EngineNode[] = view.groups.map((g) => node(`draft:group:${g.id}`, "group", "group", g.string, take(g.fields), { attrs: { col: String(g.columns * 2) } }));
  for (const nb of view.notebooks ?? []) {
    sheet.push(node(`draft:notebook:${nb.id}`, "notebook", "notebook", "", nb.pages.map((p) => node(`draft:page:${p.id}`, "page", "page", p.string, take(p.fields)))));
  }
  const kids: EngineNode[] = [];
  if (view.headerButtons?.length || view.statusbar) {
    const header = (view.headerButtons ?? []).map((b) => node(`draft:button:${b.id}`, "button", "button", b.string, [], { attrs: b.variant === "primary" ? { class: "btn-primary" } : {} }));
    if (view.statusbar) {
      header.push(node("draft:statusbar", "field", "field", "Status", [], { name: view.statusbar.field, attrs: { widget: "statusbar" } }));
      record[view.statusbar.field] = view.statusbar.activeStage ?? view.statusbar.stages[0] ?? "";
    }
    kids.push(node("draft:header", "header", "header", "", header));
  }
  kids.push(node("draft:sheet", "sheet", "sheet", "", sheet));
  return { tree: node("draft:root", "form", "root", view.title || view.model, kids), record };
}
