/**
 * PDF-05 — client mirror of apps/api/app/qweb_unsafe_gate.py.
 * Surfaces a clear human error on save/preview before the API round-trip.
 * Server gate remains authoritative.
 */

/** Stock layout keys permitted as t-call targets (keep in sync with API). */
export const QWEB_T_CALL_ALLOWLIST = new Set([
  "web.external_layout",
  "web.html_container",
  "web.basic_layout",
  "web.minimal_layout",
  "web.internal_layout",
]);

const SCRIPT_RE = /<\s*script\b/i;
const T_RAW_RE = /\bt-raw\b/i;
const T_OUT_RE = /\bt-out\b/i;
const T_CALL_RE = /\bt-call\s*=\s*(['"])(.*?)\1/gi;
const DOCTYPE_RE = /<!DOCTYPE\b/i;
const ENTITY_RE = /<!ENTITY\b/i;
const EXTERNAL_ENTITY_RE = /<!ENTITY\b[^>]*\b(?:SYSTEM|PUBLIC)\b|SYSTEM\s+(['"])[^'"]*\1/i;
const BLOCK_QWEB_RE =
  /(<\s*t[\s>/])|(\{\{)|(\}\})|(\bt-(?:raw|out|esc|call|foreach|as|if|elif|else|field|options|att|attf|set|value|lang|name|nocache|js|debug|translation)\b)/i;

export function archHasXxe(arch: string): boolean {
  if (!arch) return false;
  return DOCTYPE_RE.test(arch) || ENTITY_RE.test(arch) || EXTERNAL_ENTITY_RE.test(arch);
}

/** Return a human refusal message, or null when the arch is allowed. */
export function refuseUnsafeQwebArch(arch: string): string | null {
  if (!arch) return null;
  if (T_RAW_RE.test(arch)) {
    return "Unsafe QWeb refused: t-raw is not allowed in report templates";
  }
  if (T_OUT_RE.test(arch)) {
    return (
      "Unsafe QWeb refused: t-out is not allowed in report templates " +
      "(use grounded t-field blocks instead)"
    );
  }
  if (SCRIPT_RE.test(arch)) {
    return "Unsafe QWeb refused: <script> is not allowed in report templates";
  }
  if (archHasXxe(arch)) {
    return "Unsafe QWeb refused: XML external entities (DOCTYPE / ENTITY) are not allowed";
  }
  T_CALL_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = T_CALL_RE.exec(arch)) !== null) {
    const target = (match[2] || "").trim();
    if (!target) {
      return "Unsafe QWeb refused: empty t-call target";
    }
    if (!QWEB_T_CALL_ALLOWLIST.has(target)) {
      const allowed = [...QWEB_T_CALL_ALLOWLIST].sort().join(", ");
      return `Unsafe QWeb refused: t-call to '${target}' is not on the allowlist (${allowed})`;
    }
  }
  return null;
}

export type BlockTextSource = {
  type?: string;
  text?: string;
  label?: string;
  /** PDF-07 Table Inspector totals caption. */
  totals_label?: string;
  columns?: Array<{ label?: string; field?: string }>;
};

export function refuseUnsafeBlockText(
  blocks: BlockTextSource[] | null | undefined,
): string | null {
  if (!blocks) return null;
  for (const block of blocks) {
    const candidates: Array<[string, string]> = [];
    if (typeof block.text === "string" && block.text) {
      candidates.push(["text", block.text]);
    }
    if (typeof block.label === "string" && block.label) {
      candidates.push(["label", block.label]);
    }
    for (const col of block.columns || []) {
      if (typeof col.label === "string" && col.label) {
        candidates.push(["column.label", col.label]);
      }
    }
    if (typeof block.totals_label === "string" && block.totals_label) {
      candidates.push(["totals_label", block.totals_label]);
    }
    for (const [where, text] of candidates) {
      if (BLOCK_QWEB_RE.test(text)) {
        return (
          `Unsafe QWeb refused: ${where} must not contain QWeb ` +
          "directives or template markers"
        );
      }
    }
  }
  return null;
}

/** Combined client gate for a designer spec (blocks + optional pasted arch). */
export function refuseUnsafeReportDesign(input: {
  blocks?: BlockTextSource[];
  arch?: string | null;
}): string | null {
  const blockErr = refuseUnsafeBlockText(input.blocks);
  if (blockErr) return blockErr;
  if (input.arch) {
    return refuseUnsafeQwebArch(input.arch);
  }
  return null;
}
