import type { EngineNode, EngineOp } from "@/lib/api/view-engine";
import type { BlockType, Finding, Placement, ReportBlock2b } from "@/lib/api/view-engine-2b";

/** Error detail the API attached (409 conflicts, package problems). */
export function errorDetail(err: unknown): Record<string, unknown> | null {
  const d = err && typeof err === "object" ? (err as { detail?: unknown }).detail : null;
  return d && typeof d === "object" ? (d as Record<string, unknown>) : null;
}

export function isPublishConflict(err: unknown): boolean {
  return Boolean(errorDetail(err)?.conflict) && (err as { status?: number }).status === 409;
}

export function healthWord(score: number): { word: string; tone: "good" | "fair" | "poor" } {
  if (score >= 85) return { word: "Good", tone: "good" };
  if (score >= 65) return { word: "Fair", tone: "fair" };
  return { word: "Needs work", tone: "poor" };
}

/** Every one-click fix in a list, once each, in order. */
export function allFixOps(findings: Finding[]): EngineOp[] {
  const seen = new Set<string>();
  const out: EngineOp[] = [];
  for (const f of findings) {
    for (const op of f.ops ?? []) {
      const key = JSON.stringify(op);
      if (!seen.has(key)) {
        seen.add(key);
        out.push(op);
      }
    }
  }
  return out;
}

function walk(node: EngineNode, fn: (n: EngineNode, parent: EngineNode | null) => boolean | void, parent: EngineNode | null = null): EngineNode | null {
  if (fn(node, parent)) return node;
  for (const c of node.children ?? []) {
    const hit = walk(c, fn, node);
    if (hit) return hit;
  }
  return null;
}

export function findNode(tree: EngineNode, pred: (n: EngineNode) => boolean): EngineNode | null {
  return walk(tree, (n) => pred(n));
}

export type Placement2b = { target: string; position: "before" | "after" | "inside" } | { error: string };

const CONTAINERS = new Set(["group", "page", "sheet", "div"]);

/** Where a library element goes, from what's selected (the server re-checks every placement). */
export function placeElement(kind: string, tree: EngineNode, selected: EngineNode | null): Placement2b {
  const sheet = findNode(tree, (n) => n.tag === "sheet");
  const firstInSheet = sheet?.children.find((c) => c.anchor) ?? null;
  const atSheetTop = (): Placement2b =>
    firstInSheet ? { target: firstInSheet.id, position: "before" } : sheet ? { target: sheet.id, position: "inside" } : { target: tree.id, position: "inside" };
  switch (kind) {
    case "header":
      if (findNode(tree, (n) => n.tag === "header")) return { error: "This screen already has a header bar." };
      return sheet ? { target: sheet.id, position: "before" } : { target: tree.id, position: "inside" };
    case "chatter":
      if (findNode(tree, (n) => n.tag === "chatter" || (n.tag === "div" && (n.attrs.class ?? "").includes("oe_chatter")))) {
        return { error: "This screen already has a chatter." };
      }
      return sheet ? { target: sheet.id, position: "after" } : { target: tree.id, position: "inside" };
    case "button_box":
      if (findNode(tree, (n) => n.name === "button_box")) return { error: "This screen already has a button box." };
      return atSheetTop();
    case "ribbon":
    case "title":
      return atSheetTop();
    case "statusbar": {
      const header = findNode(tree, (n) => n.tag === "header");
      return header ? { target: header.id, position: "inside" } : { error: "Add a header bar first; the status bar goes in it." };
    }
    case "smart_button": {
      const box = findNode(tree, (n) => n.name === "button_box");
      return box ? { target: box.id, position: "inside" } : { error: "Add a button box first; smart buttons go in it." };
    }
    case "page": {
      if (selected?.tag === "notebook") return { target: selected.id, position: "inside" };
      if (selected?.tag === "page") return { target: selected.id, position: "after" };
      const nb = findNode(tree, (n) => n.tag === "notebook");
      return nb ? { target: nb.id, position: "inside" } : { error: "Add tabs first; a tab goes inside them." };
    }
    case "action_button": {
      if (tree.tag === "list" || tree.tag === "tree") return { target: tree.id, position: "inside" };
      const header = findNode(tree, (n) => n.tag === "header");
      return header ? { target: header.id, position: "inside" } : { error: "Add a header bar first; action buttons go in it." };
    }
    default: {
      if (selected && selected.kind !== "root") {
        if (CONTAINERS.has(selected.tag)) return { target: selected.id, position: "inside" };
        return { target: selected.id, position: "after" };
      }
      const group = findNode(tree, (n) => n.tag === "group" && Boolean(n.anchor));
      if (group) return { target: group.id, position: "inside" };
      return sheet ? { target: sheet.id, position: "inside" } : { target: tree.id, position: "inside" };
    }
  }
}

/** Where a new field goes: inside the selected group/tab, after a selected field, else the first group. */
export function placeField(tree: EngineNode, selected: EngineNode | null): Placement2b {
  if (tree.tag === "list" || tree.tag === "tree" || tree.tag === "search" || tree.tag === "calendar") return { target: tree.id, position: "inside" };
  return placeElement("field", tree, selected);
}

export function downloadJson(fileName: string, data: unknown): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  a.click();
  URL.revokeObjectURL(url);
}

export function editorIdentity(): { id: string; name: string } {
  if (typeof window === "undefined") return { id: "server-render", name: "Someone" };
  let id = window.sessionStorage.getItem("ingenium-editor-id");
  if (!id) {
    id = Math.random().toString(36).slice(2, 12) + Date.now().toString(36);
    window.sessionStorage.setItem("ingenium-editor-id", id);
  }
  const name = window.localStorage.getItem("ingenium-user-name") || "A teammate";
  return { id, name };
}

// ---- Reports and emails -----------------------------------------------------

export const BLOCK_LABELS: Record<BlockType, string> = {
  heading: "Heading",
  text: "Text",
  field: "Field value",
  label_field: "Label and value",
  divider: "Divider line",
  spacer: "Space",
  line_table: "Lines table with totals",
  qr: "QR code",
  barcode: "Barcode",
  signature: "Signature",
  image_field: "Picture",
  watermark: "Watermark",
  page_break: "Page break",
};

/** A sensible starting block of each type; the user fills in the rest. */
export function newBlock(type: BlockType, firstField = "name"): ReportBlock2b {
  switch (type) {
    case "heading":
      return { type, text: "New heading", level: 3 };
    case "text":
      return { type, text: "New text" };
    case "field":
    case "label_field":
    case "qr":
    case "barcode":
      return { type, field: firstField };
    case "signature":
    case "image_field":
      return { type, field: "" };
    case "line_table":
      return { type, field: "", columns: [] };
    case "watermark":
      return { type, text: "DRAFT", colour: "grey" };
    case "spacer":
      return { type, size: "medium" };
    default:
      return { type } as ReportBlock2b;
  }
}

export function addBlock(placements: Placement[], slot: string, block: ReportBlock2b): Placement[] {
  const i = placements.findIndex((p) => p.slot === slot);
  if (i < 0) return [...placements, { slot, blocks: [block] }];
  return placements.map((p, j) => (j === i ? { ...p, blocks: [...p.blocks, block] } : p));
}

export function updateBlock(placements: Placement[], slot: string, index: number, block: ReportBlock2b | null): Placement[] {
  return placements
    .map((p) => {
      if (p.slot !== slot) return p;
      const blocks = block ? p.blocks.map((b, i) => (i === index ? block : b)) : p.blocks.filter((_, i) => i !== index);
      return { ...p, blocks };
    })
    .filter((p) => p.blocks.length > 0);
}

export function moveBlock(placements: Placement[], slot: string, index: number, delta: -1 | 1): Placement[] {
  return placements.map((p) => {
    if (p.slot !== slot) return p;
    const j = index + delta;
    if (j < 0 || j >= p.blocks.length) return p;
    const blocks = [...p.blocks];
    [blocks[index], blocks[j]] = [blocks[j], blocks[index]];
    return { ...p, blocks };
  });
}

export function blockCount(placements: Placement[]): number {
  return placements.reduce((n, p) => n + p.blocks.length, 0);
}

export function pdfUrlFromB64(b64: string): string {
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  return URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
}
