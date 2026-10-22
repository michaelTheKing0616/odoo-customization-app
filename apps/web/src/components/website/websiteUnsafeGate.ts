/**
 * DOC-WEBSITE — website page arch/HTML gate in the PDF-05 / DOC-MAIL family.
 * Reuses reportUnsafeGate (client mirror of qweb_unsafe_gate) for script /
 * t-raw / t-out / XXE / t-call. Adds website honesty: no freeform invent,
 * no event-handler injection on locked XML or free HTML / href / src.
 * Locked unrecognized snippets stay verbatim but still pass the refuse gate
 * on save (no second unsafe editor).
 */

import {
  archHasXxe,
  refuseUnsafeBlockText,
  refuseUnsafeQwebArch,
} from "@/components/reports/reportUnsafeGate";

const EVENT_ATTR_RE = /\bon[a-z]+\s*=/i;
const JS_URL_RE = /(?:href|src|formaction|action)\s*=\s*(['"])\s*javascript:/i;
const DATA_HTML_RE = /(?:href|src)\s*=\s*(['"])\s*data:\s*text\/html/i;
const BARE_JS_URL_RE = /^\s*javascript:/i;
const BARE_DATA_HTML_RE = /^\s*data:\s*text\/html/i;

export type WebsiteGateBlock = {
  id?: string;
  kind?: string;
  text?: string;
  href?: string;
  src?: string;
  locked_xml?: string;
  children?: WebsiteGateBlock[];
};

/** Return a human refusal message, or null when the HTML/arch is allowed. */
export function refuseUnsafeWebsiteHtml(html: string): string | null {
  if (!html) return null;

  const qwebErr = refuseUnsafeQwebArch(html);
  if (qwebErr) {
    return qwebErr.replace(/report templates/g, "website pages");
  }
  if (archHasXxe(html)) {
    return "Unsafe website HTML refused: XML external entities (DOCTYPE / ENTITY) are not allowed";
  }
  if (EVENT_ATTR_RE.test(html)) {
    return "Unsafe website HTML refused: inline event handlers (on*) are not allowed";
  }
  if (JS_URL_RE.test(html)) {
    return "Unsafe website HTML refused: javascript: URLs are not allowed";
  }
  if (DATA_HTML_RE.test(html)) {
    return "Unsafe website HTML refused: data:text/html URLs are not allowed";
  }
  return null;
}

function refuseUnsafeUrl(value: string, where: string): string | null {
  if (!value) return null;
  if (BARE_JS_URL_RE.test(value)) {
    return `Unsafe website ${where} refused: javascript: URLs are not allowed`;
  }
  if (BARE_DATA_HTML_RE.test(value)) {
    return `Unsafe website ${where} refused: data:text/html URLs are not allowed`;
  }
  return null;
}

/** Walk editable + locked blocks; refuse QWeb invent in text and unsafe locked XML. */
export function refuseUnsafeWebsiteBlocks(
  blocks: WebsiteGateBlock[] | null | undefined,
): string | null {
  if (!blocks?.length) return null;

  for (const block of blocks) {
    const kind = block.kind || "locked";

    if (kind === "locked") {
      const lockedErr = refuseUnsafeWebsiteHtml(block.locked_xml || "");
      if (lockedErr) return lockedErr;
    }

    if (typeof block.text === "string" && block.text) {
      const textErr = refuseUnsafeBlockText([
        { type: kind, text: block.text },
      ]);
      if (textErr) {
        return textErr.replace(/report templates/g, "website pages").replace(
          /Unsafe QWeb refused:/,
          "Unsafe website content refused:",
        );
      }
    }

    const hrefErr = refuseUnsafeUrl(block.href || "", "href");
    if (hrefErr) return hrefErr;
    const srcErr = refuseUnsafeUrl(block.src || "", "src");
    if (srcErr) return srcErr;

    // Free HTML pasted into editable fields (beyond QWeb markers).
    for (const field of [block.text, block.href, block.src] as const) {
      if (!field) continue;
      if (EVENT_ATTR_RE.test(field) || /<\s*script\b/i.test(field)) {
        return "Unsafe website content refused: script or event handlers are not allowed in editable fields";
      }
    }

    if (block.children?.length) {
      const childErr = refuseUnsafeWebsiteBlocks(block.children);
      if (childErr) return childErr;
    }
  }
  return null;
}

/** Combined client gate for save (blocks + optional compiled arch). */
export function refuseUnsafeWebsiteSave(input: {
  blocks?: WebsiteGateBlock[] | null;
  arch?: string | null;
}): string | null {
  const blockErr = refuseUnsafeWebsiteBlocks(input.blocks);
  if (blockErr) return blockErr;
  if (input.arch) return refuseUnsafeWebsiteHtml(input.arch);
  return null;
}

/** Preview-only strip — never a substitute for the refuse gate on save. */
export function sanitizeWebsiteHtmlForPreview(html: string): string {
  if (!html) return "";
  let out = html;
  out = out.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, "");
  out = out.replace(/<(iframe|object|embed|link|meta)\b[^>]*>/gi, "");
  out = out.replace(/\son[a-z]+\s*=\s*(['"])[\s\S]*?\1/gi, "");
  out = out.replace(/\son[a-z]+\s*=\s*[^\s>]+/gi, "");
  out = out.replace(
    /(href|src|formaction|action)\s*=\s*(['"])\s*javascript:[\s\S]*?\2/gi,
    '$1="#"',
  );
  return out;
}
