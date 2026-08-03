#!/usr/bin/env node
/** One-shot bulk replace legacy hex Tailwind classes with kit token utilities. */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src");

const ALLOWLIST = new Set([
  "components/designer/FormCanvas.tsx",
  "components/designer/KanbanCardPreview.tsx",
  "components/designer/NicheWidgetPalette.tsx",
  "components/designer/DesignerFieldInspector.tsx",
  "components/designer/PropsInspector.tsx",
  "components/designer/FieldPalette.tsx",
  "components/reports/ReportCanvas.tsx",
  "app/e2e/designer/page.tsx",
  "app/globals.css",
]);

const REPLACEMENTS = [
  [/border-\[#c9a9c0\]/g, "border-border-subtle"],
  [/border-\[#c9a9c0\]\/40/g, "border-border-subtle/40"],
  [/border-\[#f0a8a0\]/g, "border-danger/50"],
  [/ring-\[#c9a9c0\]/g, "ring-accent"],
  [/ring-1 ring-\[#c9a9c0\]/g, "ring-1 ring-accent"],
  [/ring-2 ring-\[#c9a9c0\]/g, "ring-2 ring-accent"],
  [/text-\[var\(--odoo-primary-light\)\]/g, "text-accent"],
  [/text-\[var\(--odoo-primary\)\]/g, "text-accent"],
  [/bg-\[var\(--odoo-primary\)\]/g, "bg-accent"],
  [/border-\[var\(--odoo-primary\)\]/g, "border-accent"],
  [/bg-\[#0f1a16\]/g, "bg-surface-muted"],
  [/text-\[#f5eef3\]/g, "text-ink"],
  [/bg-\[#1a2e28\]/g, "bg-surface-muted"],
  [/bg-\[#f0a8a0\]/g, "bg-danger"],
  [/text-\[#1a100c\]/g, "text-white"],
  [/border-b-2 border-\[#c9a9c0\]/g, "border-b-2 border-border-subtle"],
  [/border-\[#8f7a88\]/g, "border-border-subtle"],
  [/border-\[#5a3a36\]/g, "border-danger/40"],
  [/border-\[#a85b4a\]/g, "border-danger/50"],
  [/bg-\[#0c090b\]/g, "bg-surface"],
  [/bg-\[#0c090b\]\/80/g, "bg-background/80"],
  [/bg-\[#1a1218\]/g, "bg-surface-raised"],
  [/bg-\[#2a1512\]/g, "bg-danger-subtle"],
  [/bg-\[#3d2a38\]/g, "bg-surface-muted"],
  [/bg-\[#714[Bb]67\]/g, "bg-accent"],
  [/bg-\[#a85b4a\]/g, "bg-danger"],
  [/text-\[#f4eef2\]/g, "text-ink"],
  [/text-\[#c9a9c0\]/g, "text-muted"],
  [/text-\[#8f7a88\]/g, "text-muted"],
  [/text-\[#e8cfc9\]/g, "text-ink"],
  [/text-\[#f0a8a0\]/g, "text-danger"],
  [/text-\[#d4c4ce\]/g, "text-muted"],
  [/text-\[#714[Bb]67\]/g, "text-accent"],
  [/hover:bg-\[#714[Bb]67\]/g, "hover:bg-accent-hover"],
  [/hover:bg-\[#1a1218\]/g, "hover:bg-surface-muted"],
  [/hover:text-\[#f4eef2\]/g, "hover:text-ink"],
  [/focus:border-\[#f0a8a0\]/g, "focus-visible:ring-2 focus-visible:ring-danger"],
  [/outline-none focus:border-\[#714[Bb]67\]/g, "outline-none focus-visible:ring-2 focus-visible:ring-accent"],
];

function walk(dir, out = []) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    const st = fs.statSync(full);
    if (st.isDirectory()) walk(full, out);
    else if (/\.tsx$/.test(name)) out.push(full);
  }
  return out;
}

let changed = 0;
for (const file of walk(ROOT)) {
  const rel = path.relative(ROOT, file).replace(/\\/g, "/");
  if (ALLOWLIST.has(rel)) continue;
  let text = fs.readFileSync(file, "utf8");
  const before = text;
  for (const [re, rep] of REPLACEMENTS) {
    text = text.replace(re, rep);
  }
  if (text !== before) {
    fs.writeFileSync(file, text);
    changed++;
    console.log("updated", rel);
  }
}
console.log(`Done — ${changed} files updated.`);
