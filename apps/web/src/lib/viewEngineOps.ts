/**
 * Client helpers for the shared view engine. The server compiles and authorizes
 * every change; these helpers only decide what the UI offers and how it reads.
 * Nesting rules mirror apps/api/app/view_engine.py ALLOWED_PARENTS.
 */
import type { EngineNode, EngineOp } from "@/lib/api/view-engine";

export type DropPosition = "before" | "after" | "inside";

const ALLOWED_PARENTS: Record<string, string[]> = {
  field: ["group", "page", "sheet", "div", "list", "tree", "kanban", "header", "form"],
  group: ["sheet", "page", "group", "div", "form"],
  page: ["notebook"],
  notebook: ["sheet", "page", "div", "form"],
  button: ["header", "div", "group", "list", "tree"],
  separator: ["group", "page", "sheet", "div"],
  label: ["group", "page", "sheet", "div"],
  div: ["sheet", "page", "group", "div", "form"],
};

const PLAIN_TAG: Record<string, string> = {
  group: "group",
  page: "tab",
  notebook: "set of tabs",
  sheet: "form body",
  header: "header bar",
  div: "box",
  list: "list",
  tree: "list",
  kanban: "card view",
  form: "form",
  field: "field",
  button: "button",
};

export function plainTag(tag: string): string {
  return PLAIN_TAG[tag] ?? tag;
}

export type TreeIndex = {
  byId: Map<string, EngineNode>;
  parentOf: Map<string, string>;
};

export function indexTree(root: EngineNode): TreeIndex {
  const byId = new Map<string, EngineNode>();
  const parentOf = new Map<string, string>();
  const walk = (node: EngineNode) => {
    byId.set(node.id, node);
    for (const child of node.children) {
      parentOf.set(child.id, node.id);
      walk(child);
    }
  };
  walk(root);
  return { byId, parentOf };
}

function isAncestor(index: TreeIndex, maybeAncestor: string, nodeId: string): boolean {
  let cur: string | undefined = nodeId;
  while (cur) {
    if (cur === maybeAncestor) return true;
    cur = index.parentOf.get(cur);
  }
  return false;
}

/** Whether a node (or a new field when nodeId is null) may be dropped here. */
export function canDrop(
  index: TreeIndex,
  nodeTag: string,
  nodeId: string | null,
  targetId: string,
  position: DropPosition,
): { ok: boolean; reason?: string } {
  const target = index.byId.get(targetId);
  if (!target) return { ok: false, reason: "That place is gone. Reload the screen." };
  if (!target.anchor) return { ok: false, reason: target.locked_reason ?? "This place can't be targeted safely." };
  if (nodeId) {
    const node = index.byId.get(nodeId);
    if (!node?.anchor) return { ok: false, reason: node?.locked_reason ?? "This item can't be moved safely." };
    if (nodeId === targetId) return { ok: false, reason: "Pick a different place." };
    if (isAncestor(index, nodeId, targetId)) return { ok: false, reason: "It can't go inside itself." };
  }
  const parentId = position === "inside" ? targetId : index.parentOf.get(targetId);
  const parent = parentId ? index.byId.get(parentId) : undefined;
  if (!parent) return { ok: false, reason: "Nothing can go outside the whole screen." };
  const allowed = ALLOWED_PARENTS[nodeTag];
  if (allowed && !allowed.includes(parent.tag)) {
    return { ok: false, reason: `A ${plainTag(nodeTag)} can't go inside a ${plainTag(parent.tag)}.` };
  }
  return { ok: true };
}

export function nodeName(node: EngineNode | undefined): string {
  if (!node) return "this item";
  return node.label || plainTag(node.tag);
}

/** "Insert after Mobile" style label for the drop target. */
export function dropLabel(target: EngineNode | undefined, position: DropPosition, adding: boolean): string {
  const verb = adding ? "Add" : "Move";
  const where = position === "inside" ? "into" : position;
  return `${verb} ${where} ${nodeName(target)}`;
}

/** Plain sentence for an op, used in undo toasts and the change list. */
export function describeOp(op: EngineOp, index: TreeIndex, fieldLabel: (name: string) => string): string {
  switch (op.op) {
    case "move":
      return `Moved ${nodeName(index.byId.get(op.node))} ${op.position === "inside" ? "into" : op.position} ${nodeName(index.byId.get(op.target))}`;
    case "insert_field":
      return `Added ${fieldLabel(op.field)}`;
    case "hide":
      return `Hid ${nodeName(index.byId.get(op.node))}`;
    case "set_attr": {
      const name = nodeName(index.byId.get(op.node));
      if (op.attr === "string") return `Renamed ${name} to ${op.value}`;
      if (op.attr === "required") return op.value === "1" ? `Made ${name} required` : `Made ${name} optional`;
      if (op.attr === "readonly") return op.value === "1" ? `Made ${name} read-only` : `Made ${name} editable`;
      if (op.attr === "invisible") return op.value === "1" ? `Hid ${name}` : `Showed ${name}`;
      return `Changed ${name}`;
    }
    case "wrap":
      return `Put ${op.nodes.length} item${op.nodes.length === 1 ? "" : "s"} in a new ${plainTag(op.kind)}`;
    case "set_condition": {
      const name = nodeName(index.byId.get(op.node));
      if (op.copy_from) return `Copied the rule from ${nodeName(index.byId.get(op.copy_from))} to ${name}`;
      if (!op.condition) return `Removed the rule on ${name}`;
      return `Changed when ${name} ${op.attr === "required" ? "must be filled in" : op.attr === "readonly" ? "is read-only" : "shows"}`;
    }
    case "set_access": {
      const name = nodeName(index.byId.get(op.node));
      return op.edit.length || op.see.length ? `Changed who can see ${name}` : `${name} is visible to everyone again`;
    }
    default:
      return "Changed the screen";
  }
}

/** Keyboard reorder: Alt+Up/Down among siblings, Alt+Left out of the parent, Alt+Right into the previous group. */
export function keyboardMove(
  index: TreeIndex,
  nodeId: string,
  key: "ArrowUp" | "ArrowDown" | "ArrowLeft" | "ArrowRight",
): EngineOp | null {
  const node = index.byId.get(nodeId);
  const parentId = index.parentOf.get(nodeId);
  const parent = parentId ? index.byId.get(parentId) : undefined;
  if (!node?.anchor || !parent) return null;
  const siblings = parent.children;
  const i = siblings.findIndex((c) => c.id === nodeId);
  const candidates: Array<{ target: string; position: DropPosition }> = [];
  if (key === "ArrowUp") {
    for (let j = i - 1; j >= 0; j -= 1) candidates.push({ target: siblings[j].id, position: "before" });
  } else if (key === "ArrowDown") {
    for (let j = i + 1; j < siblings.length; j += 1) candidates.push({ target: siblings[j].id, position: "after" });
  } else if (key === "ArrowLeft") {
    candidates.push({ target: parent.id, position: "after" });
  } else {
    for (let j = i - 1; j >= 0; j -= 1) {
      if (["group", "page", "div"].includes(siblings[j].tag)) {
        candidates.push({ target: siblings[j].id, position: "inside" });
        break;
      }
    }
  }
  for (const c of candidates) {
    if (canDrop(index, node.tag, node.id, c.target, c.position).ok) {
      return { op: "move", node: node.id, target: c.target, position: c.position };
    }
  }
  return null;
}

/** Field count per tab, for the tab badges. */
export function fieldCount(node: EngineNode): number {
  let n = 0;
  const walk = (x: EngineNode) => {
    if (x.tag === "field") n += 1;
    else x.children.forEach(walk);
  };
  node.children.forEach(walk);
  return n;
}

/** Fields of the record type not yet on the screen, sorted by label. */
export function fieldsNotOnScreen(
  index: TreeIndex,
  fields: Record<string, { string?: string; type?: string }>,
  query: string,
): Array<{ name: string; label: string; type: string }> {
  const q = query.trim().toLowerCase();
  const on = new Set<string>();
  index.byId.forEach((n) => {
    if (n.tag === "field" && n.name && n.id.startsWith("field:")) on.add(n.name);
  });
  return Object.entries(fields)
    .filter(([name, f]) => !on.has(name) && !["binary", "properties", "properties_definition", "json"].includes(f.type ?? "") && !name.startsWith("__"))
    .map(([name, f]) => ({ name, label: f.string || name, type: f.type || "char" }))
    .filter((f) => !q || f.label.toLowerCase().includes(q) || f.name.toLowerCase().includes(q))
    .sort((a, b) => a.label.localeCompare(b.label))
    .slice(0, 60);
}

/** Who can see / when hidden, in plain words, for the chip bar. */
export function visibilityChips(node: EngineNode): string[] {
  const chips: string[] = [];
  const inv = node.attrs.invisible ?? node.attrs.column_invisible;
  if (inv === "1" || inv === "True") chips.push("Hidden");
  else if (inv) chips.push("Shown only sometimes");
  else chips.push("Always shown");
  if (node.attrs.groups) chips.push("Some roles only");
  else chips.push("Everyone who can open this");
  if (node.attrs.readonly === "1" || node.attrs.readonly === "True") chips.push("Read-only");
  if (node.attrs.required === "1" || node.attrs.required === "True") chips.push("Required");
  return chips;
}
