#!/usr/bin/env node
/**
 * REM-5 gate: legacy mint/plum hex and --odoo-primary must not appear outside
 * Odoo-preview surfaces (designer canvas components + e2e harness + token aliases).
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src");
const PATTERN =
  /--odoo-primary|#714[Bb]67|#0c090b|#c9a9c0|#8f7a88|#3d2a38|#1a1218|#f4eef2|#a85b4a|#2a1512|#e8cfc9|#f0a8a0|#5a3a36|#d4c4ce/;

const ALLOWLIST = [
  "components/designer/FormCanvas.tsx",
  "components/designer/KanbanCardPreview.tsx",
  "components/designer/NicheWidgetPalette.tsx",
  "components/designer/DesignerFieldInspector.tsx",
  "components/designer/PropsInspector.tsx",
  "components/designer/FieldPalette.tsx",
  "components/reports/ReportCanvas.tsx",
  "app/e2e/designer/page.tsx",
  "app/globals.css",
];

function walk(dir, out = []) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    const st = fs.statSync(full);
    if (st.isDirectory()) walk(full, out);
    else if (/\.(tsx?|css)$/.test(name)) out.push(full);
  }
  return out;
}

const hits = [];
for (const file of walk(ROOT)) {
  const rel = path.relative(ROOT, file).replace(/\\/g, "/");
  if (ALLOWLIST.some((a) => rel === a || rel.endsWith(a))) continue;
  const text = fs.readFileSync(file, "utf8");
  const lines = text.split("\n");
  lines.forEach((line, i) => {
    if (PATTERN.test(line)) {
      hits.push(`${rel}:${i + 1}: ${line.trim().slice(0, 120)}`);
    }
  });
}

if (hits.length) {
  console.error(`Legacy color violations (${hits.length}):`);
  hits.forEach((h) => console.error(h));
  process.exit(1);
}
console.log("Legacy color check passed (outside Odoo-preview surfaces).");
