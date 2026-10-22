/**
 * DOC-QWEB — compile / parse grounded QWeb view blocks ↔ arch fragment.
 * Prefer structured blocks on the paper; fall back to Source XML tab.
 */

export type QwebViewBlock =
  | { id: string; kind: "heading"; text: string; level?: 1 | 2 | 3 }
  | { id: string; kind: "paragraph"; text: string }
  | { id: string; kind: "field"; field: string }
  | { id: string; kind: "divider" }
  | { id: string; kind: "locked"; locked_xml: string };

let _seq = 0;
export function newQwebBlockId(prefix = "qb"): string {
  _seq += 1;
  return `${prefix}-${Date.now().toString(36)}-${_seq}`;
}

export function escapeXmlText(text: string): string {
  return (text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function fieldExpr(field: string, recordVar = "doc"): string {
  const path = (field || "display_name").trim() || "display_name";
  if (path.startsWith(`${recordVar}.`)) return path;
  return `${recordVar}.${path}`;
}

export function compileQwebViewBlocks(
  blocks: QwebViewBlock[],
  opts?: { wrapExternalLayout?: boolean; recordVar?: string },
): string {
  const recordVar = opts?.recordVar || "doc";
  const parts: string[] = ['<div class="page">'];
  for (const block of blocks) {
    if (block.kind === "heading") {
      const level = block.level === 1 ? 1 : block.level === 3 ? 3 : 2;
      parts.push(`<h${level}>${escapeXmlText(block.text)}</h${level}>`);
    } else if (block.kind === "paragraph") {
      parts.push(`<p>${escapeXmlText(block.text)}</p>`);
    } else if (block.kind === "field") {
      const expr = fieldExpr(block.field, recordVar);
      parts.push(`<span t-field="${escapeXmlText(expr)}"/>`);
    } else if (block.kind === "divider") {
      parts.push("<hr/>");
    } else if (block.kind === "locked" && block.locked_xml) {
      parts.push(block.locked_xml);
    }
  }
  parts.push("</div>");
  const inner = parts.join("\n");
  if (!opts?.wrapExternalLayout) return inner;
  return (
    `<t t-name="ingenium.qweb_view_primary">\n` +
    `  <t t-call="web.external_layout">\n` +
    `    ${inner}\n` +
    `  </t>\n` +
    `</t>`
  );
}

export function compileInheritFragment(
  blocks: QwebViewBlock[],
  opts: { xpath: string; position?: string; recordVar?: string },
): string {
  const xpath = (opts.xpath || "").trim();
  const position = (opts.position || "inside").trim() || "inside";
  if (!xpath) throw new Error("inherit xpath is required");
  if (/["<&]/.test(xpath)) {
    throw new Error(
      "inherit xpath must not contain quotes, <, or & — use hasclass() with single quotes",
    );
  }
  const body = compileQwebViewBlocks(blocks, {
    wrapExternalLayout: false,
    recordVar: opts.recordVar,
  });
  let bodyInner = body;
  if (bodyInner.startsWith('<div class="page">') && bodyInner.endsWith("</div>")) {
    bodyInner = bodyInner.slice('<div class="page">'.length, -"</div>".length).trim();
  }
  return (
    `<data>\n` +
    `  <xpath expr="${xpath}" position="${position}">\n` +
    `    ${bodyInner}\n` +
    `  </xpath>\n` +
    `</data>`
  );
}

/**
 * Best-effort parse for Ingenium-authored page fragments.
 * Complex / foreign arches return null → editor stays on Source XML.
 */
export function tryParseQwebViewBlocks(arch: string): QwebViewBlock[] | null {
  const trimmed = (arch || "").trim();
  if (!trimmed) return [];

  let inner = trimmed;
  const wrappers = [
    /<t\b[^>]*t-call\s*=\s*['"]web\.external_layout['"][^>]*>([\s\S]*)<\/t>/i,
    /<t\b[^>]*t-name\s*=\s*['"][^'"]+['"][^>]*>([\s\S]*)<\/t>/i,
    /<template\b[^>]*>([\s\S]*)<\/template>/i,
    /<div\b[^>]*class=["'][^"']*\bpage\b[^"']*["'][^>]*>([\s\S]*)<\/div>/i,
  ];
  for (const re of wrappers) {
    const m = re.exec(inner);
    if (m) {
      inner = m[1].trim();
      break;
    }
  }

  if (/<(table|ul|ol|blockquote|xpath|data)\b/i.test(inner)) return null;

  const blocks: QwebViewBlock[] = [];
  const tokenRe =
    /<(h[1-3]|p|hr)\b[^>]*>([\s\S]*?)<\/\1>|<hr\s*\/?>|<\s*(?:span|div|t)\b[^>]*\bt-field\s*=\s*(['"])(.*?)\3[^>]*\/?\s*>/gi;

  let cursor = 0;
  let m: RegExpExecArray | null;
  const matches: Array<{ index: number; end: number; block: QwebViewBlock }> = [];
  while ((m = tokenRe.exec(inner)) !== null) {
    const full = m[0];
    if (/^<hr/i.test(full)) {
      matches.push({
        index: m.index,
        end: m.index + full.length,
        block: { id: newQwebBlockId("hr"), kind: "divider" },
      });
      continue;
    }
    if (/\bt-field\b/i.test(full)) {
      const raw = (m[4] || "").trim();
      let field = raw.startsWith("doc.") ? raw.slice(4) : raw;
      if (field.startsWith("o.")) field = field.slice(2);
      matches.push({
        index: m.index,
        end: m.index + full.length,
        block: { id: newQwebBlockId("f"), kind: "field", field },
      });
      continue;
    }
    const tag = (m[1] || "").toLowerCase();
    const plain = decodeBasicEntities((m[2] || "").replace(/<[^>]+>/g, "")).trim();
    if (tag === "h1" || tag === "h2" || tag === "h3") {
      matches.push({
        index: m.index,
        end: m.index + full.length,
        block: {
          id: newQwebBlockId("h"),
          kind: "heading",
          text: plain,
          level: Number(tag.slice(1)) as 1 | 2 | 3,
        },
      });
    } else if (tag === "p") {
      matches.push({
        index: m.index,
        end: m.index + full.length,
        block: { id: newQwebBlockId("p"), kind: "paragraph", text: plain },
      });
    }
  }

  if (matches.length === 0) return null;

  // Whole string must be only these tags (+ whitespace).
  let rebuilt = "";
  for (const item of matches) {
    if (item.index < cursor) return null;
    const gap = inner.slice(cursor, item.index).replace(/\s+/g, "");
    if (gap.length > 0) return null;
    rebuilt += inner.slice(item.index, item.end);
    blocks.push(item.block);
    cursor = item.end;
  }
  if (inner.slice(cursor).replace(/\s+/g, "").length > 0) return null;
  void rebuilt;
  return blocks;
}

function decodeBasicEntities(s: string): string {
  return s
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&");
}

export function defaultQwebViewBlocks(title = "Document"): QwebViewBlock[] {
  return [
    { id: newQwebBlockId("h"), kind: "heading", text: title, level: 2 },
    {
      id: newQwebBlockId("p"),
      kind: "paragraph",
      text: "Grounded QWeb document — edit blocks or open Source XML.",
    },
    { id: newQwebBlockId("f"), kind: "field", field: "display_name" },
  ];
}

/** Preview HTML chips (not live Odoo merge). */
export function blocksToPreviewHtml(blocks: QwebViewBlock[]): string {
  const parts: string[] = [];
  for (const b of blocks) {
    if (b.kind === "heading") {
      const level = b.level === 1 ? 1 : b.level === 3 ? 3 : 2;
      parts.push(`<h${level}>${escapeXmlText(b.text)}</h${level}>`);
    } else if (b.kind === "paragraph") {
      parts.push(`<p>${escapeXmlText(b.text)}</p>`);
    } else if (b.kind === "field") {
      parts.push(
        `<span class="qweb-field-chip">doc.${escapeXmlText(b.field || "display_name")}</span>`,
      );
    } else if (b.kind === "divider") {
      parts.push("<hr/>");
    } else if (b.kind === "locked") {
      parts.push(
        `<pre class="qweb-locked">${escapeXmlText(b.locked_xml || "").slice(0, 240)}</pre>`,
      );
    }
  }
  return parts.join("\n") || "<p><em>Empty document</em></p>";
}
