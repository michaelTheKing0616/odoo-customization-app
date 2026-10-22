/** Request bodies for extending a built-in (stock) Odoo model. Pure, so tests and the live check share them. */

export type ExtendViewInput = {
  model: string;
  viewType: "form" | "list";
  op: "add" | "move";
  field: string;
  /** Existing form field to place it after. Empty = end of the screen. */
  after: string;
};

/**
 * First match in document order: what Odoo itself picks for a plain //field locator, written so the
 * overlay check sees exactly one node (built-in forms repeat fields in nested child forms).
 */
const fieldExpr = (name: string) => `(//field[@name='${name}'])[1]`;

/** Body for the Designer overlay route: always an extension view on top of the original. */
export function overlayBody(i: ExtendViewInput): Record<string, unknown> {
  if (i.op === "move") {
    return { model: i.model, view_type: i.viewType, operation: "move", expr: fieldExpr(i.field),
      anchor_expr: fieldExpr(i.after), move_position: "after" };
  }
  return i.after
    ? { model: i.model, view_type: i.viewType, operation: "add_field", expr: fieldExpr(i.after),
        add_field_name: i.field, add_position: "after" }
    : { model: i.model, view_type: i.viewType, operation: "add_field", expr: "/*",
        add_field_name: i.field, add_position: "inside" };
}

export type AutomationInput = {
  model: string;
  name: string;
  when: "created" | "updated" | "date";
  dateField?: string;
  days?: number;
  direction?: "before" | "after";
  action: "todo" | "set";
  summary?: string;
  /** many2one res.users field on the record that owns the to-do. */
  userField?: string;
  setField?: string;
  setValue?: string;
};

/** App plan with one automation; Apply runs the same checks as App Studio (version, date field, owner). */
export function automationSpec(i: AutomationInput): Record<string, unknown> {
  const trigger = i.when === "created" ? "on_create" : i.when === "updated" ? "on_write" : "on_time";
  const timing = i.when === "date"
    ? { trg_date_field_name: i.dateField, trg_date_range: i.days ?? 1, trg_date_range_type: "day",
        trg_date_range_mode: i.direction ?? "before" }
    : {};
  const action = i.action === "todo"
    ? { kind: "next_activity", summary: i.summary || i.name, user_type: "generic", activity_user_field_name: i.userField }
    : { kind: "update_field", field_name: i.setField, value: i.setValue ?? "" };
  return {
    technical_name: `overview_auto_${i.model.replace(/\./g, "_")}`,
    display_name: i.name,
    models: [],
    automations: [{ name: i.name, model: i.model, trigger, ...timing, safe_actions: [action] }],
  };
}

export type AccessInput = {
  model: string;
  group: string;
  read: boolean; write: boolean; create: boolean; remove: boolean;
  ownOnly: boolean;
};

/** App plan with one access rule. Odoo 20 writes ir.access (with domain); 17-19 write ir.model.access + ir.rule. */
export function accessSpec(i: AccessInput): Record<string, unknown> {
  const stem = `${i.model.replace(/\./g, "_")}_${i.group.split(".").pop()}${i.ownOnly ? "_own" : ""}`;
  return {
    technical_name: `overview_access_${i.model.replace(/\./g, "_")}`,
    display_name: i.model,
    models: [],
    access_rules: [{
      name: `access_${stem}`, model: i.model, group: i.group,
      perm_read: i.read, perm_write: i.write, perm_create: i.create, perm_unlink: i.remove,
      ...(i.ownOnly ? { domain: "[('create_uid', '=', user.id)]" } : {}),
    }],
  };
}

export const ACCESS_GROUPS = [
  { value: "base.group_user", label: "Internal users" },
  { value: "base.group_portal", label: "Portal users" },
  { value: "base.group_system", label: "Administrators" },
];
