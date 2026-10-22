/**
 * DOC-MAIL — compile / parse simple mail body blocks ↔ HTML.
 * Prefer structured blocks on the paper; fall back to raw HTML source tab.
 */

export type MailBodyBlock =
  | { id: string; type: "heading"; text: string; level?: 1 | 2 }
  | { id: string; type: "paragraph"; text: string }
  | { id: string; type: "field"; field: string };

let _seq = 0;
export function newMailBlockId(prefix = "mb"): string {
  _seq += 1;
  return `${prefix}-${Date.now().toString(36)}-${_seq}`;
}

export function escapeHtmlText(text: string): string {
  return (text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function compileMailBodyBlocks(blocks: MailBodyBlock[]): string {
  const parts: string[] = [];
  for (const block of blocks) {
    if (block.type === "heading") {
      const level = block.level === 1 ? 1 : 2;
      parts.push(`<h${level}>${escapeHtmlText(block.text)}</h${level}>`);
    } else if (block.type === "paragraph") {
      parts.push(`<p>${escapeHtmlText(block.text)}</p>`);
    } else if (block.type === "field") {
      const field = (block.field || "").trim();
      if (field) parts.push(`<p>{{ object.${field} }}</p>`);
    }
  }
  return parts.join("\n") || "<p></p>";
}

/**
 * Best-effort parse for common Ingenium-authored bodies.
 * Complex / foreign HTML returns null → editor stays on source tab.
 */
export function tryParseMailBodyBlocks(html: string): MailBodyBlock[] | null {
  const trimmed = (html || "").trim();
  if (!trimmed) return [];
  if (/<(table|ul|ol|blockquote|div)\b/i.test(trimmed)) return null;

  const blocks: MailBodyBlock[] = [];
  const re = /<(h1|h2|p)\b[^>]*>([\s\S]*?)<\/\1>/gi;
  let m: RegExpExecArray | null;
  const matches: Array<{ tag: string; inner: string; full: string }> = [];
  while ((m = re.exec(trimmed)) !== null) {
    matches.push({ tag: m[1].toLowerCase(), inner: m[2], full: m[0] });
  }
  if (matches.length === 0) return null;

  // Whole string must be only these tags (+ whitespace between).
  const remainder = trimmed
    .replace(/<(h1|h2|p)\b[^>]*>([\s\S]*?)<\/\1>/gi, "")
    .replace(/\s+/g, "");
  if (remainder.length > 0) return null;

  for (const match of matches) {
    const plain = decodeBasicEntities(match.inner.replace(/<[^>]+>/g, "")).trim();
    const fieldMatch = /^\{\{\s*object\.([a-zA-Z_][\w]*)\s*\}\}$/.exec(plain);
    if (match.tag === "p" && fieldMatch) {
      blocks.push({
        id: newMailBlockId("field"),
        type: "field",
        field: fieldMatch[1],
      });
      continue;
    }
    if (match.tag === "h1" || match.tag === "h2") {
      blocks.push({
        id: newMailBlockId("h"),
        type: "heading",
        text: plain,
        level: match.tag === "h1" ? 1 : 2,
      });
    } else {
      blocks.push({ id: newMailBlockId("p"), type: "paragraph", text: plain });
    }
  }
  return blocks;
}

function decodeBasicEntities(s: string): string {
  return s
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&");
}

export function defaultMailBlocks(name = "Hello"): MailBodyBlock[] {
  return [
    { id: newMailBlockId("h"), type: "heading", text: name, level: 2 },
    {
      id: newMailBlockId("p"),
      type: "paragraph",
      text: "Thank you for your business.",
    },
    { id: newMailBlockId("field"), type: "field", field: "display_name" },
  ];
}
