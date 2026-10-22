/**
 * DOC-QWEB — general QWeb view gate in the PDF-05 family.
 * Reuses reportUnsafeGate for script / t-raw / t-out / XXE patterns, then
 * applies general-QWeb honesty: on* / javascript: / data:text/html, plus
 * grandfathered t-call targets from the loaded arch (no invent).
 */

import {
  archHasXxe,
  QWEB_T_CALL_ALLOWLIST,
} from "@/components/reports/reportUnsafeGate";

const SCRIPT_RE = /<\s*script\b/i;
const T_RAW_RE = /\bt-raw\b/i;
const T_OUT_RE = /\bt-out\b/i;
const T_CALL_RE = /\bt-call\s*=\s*(['"])(.*?)\1/gi;
const EVENT_ATTR_RE = /\bon[a-z]+\s*=/i;
const JS_URL_RE = /(?:href|src)\s*=\s*(['"])\s*javascript:/i;
const DATA_HTML_RE = /(?:href|src)\s*=\s*(['"])\s*data:\s*text\/html/i;
const BLOCK_QWEB_RE =
  /(<\s*t[\s>/])|(\{\{)|(\}\})|(\bt-(?:raw|out|esc|call|foreach|as|if|elif|else|field|options|att|attf|set|value|lang|name|nocache|js|debug|translation)\b)/i;

const ROOT_REPLACE_EXPRS = new Set([
  "/",
  "/*",
  "/t",
  "/t[1]",
  "//t",
  "/template",
  "//template",
  ".",
  "//*",
  "//form",
  "//sheet",
  "//list",
  "//tree",
  "//div",
  "//page",
]);

export function extractTCallTargets(arch: string): string[] {
  if (!arch) return [];
  const out = new Set<string>();
  T_CALL_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = T_CALL_RE.exec(arch)) !== null) {
    const target = (match[2] || "").trim();
    if (target) out.add(target);
  }
  return [...out].sort();
}

/** Return a human refusal message, or null when the arch is allowed. */
export function refuseUnsafeQwebViewArch(
  arch: string,
  opts?: { allowExistingTCalls?: Iterable<string> | null },
): string | null {
  if (!arch) return null;
  if (T_RAW_RE.test(arch)) {
    return "Unsafe QWeb refused: t-raw is not allowed in general QWeb views";
  }
  if (T_OUT_RE.test(arch)) {
    return (
      "Unsafe QWeb refused: t-out is not allowed in general QWeb views " +
      "(use grounded t-field blocks instead)"
    );
  }
  if (SCRIPT_RE.test(arch)) {
    return "Unsafe QWeb refused: <script> is not allowed in general QWeb views";
  }
  if (archHasXxe(arch)) {
    return "Unsafe QWeb refused: XML external entities (DOCTYPE / ENTITY) are not allowed";
  }
  if (EVENT_ATTR_RE.test(arch)) {
    return "Unsafe QWeb refused: inline event handlers (on*) are not allowed";
  }
  if (JS_URL_RE.test(arch)) {
    return "Unsafe QWeb refused: javascript: URLs are not allowed";
  }
  if (DATA_HTML_RE.test(arch)) {
    return "Unsafe QWeb refused: data:text/html URLs are not allowed";
  }

  const allowed = new Set<string>(QWEB_T_CALL_ALLOWLIST);
  if (opts?.allowExistingTCalls) {
    for (const t of opts.allowExistingTCalls) {
      if (t) allowed.add(t);
    }
  }

  T_CALL_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = T_CALL_RE.exec(arch)) !== null) {
    const target = (match[2] || "").trim();
    if (!target) return "Unsafe QWeb refused: empty t-call target";
    if (!allowed.has(target)) {
      const stock = [...QWEB_T_CALL_ALLOWLIST].sort().join(", ");
      return (
        `Unsafe QWeb refused: t-call to '${target}' is not on the allowlist ` +
        `and was not present on the loaded arch (${stock})`
      );
    }
  }
  return null;
}

export function refuseRootReplace(
  xpath: string,
  position: string,
): string | null {
  if (String(position).trim().toLowerCase() !== "replace") return null;
  const norm = String(xpath).replace(/\s+/g, "");
  if (ROOT_REPLACE_EXPRS.has(norm)) {
    return "xpath replaces the root or a large subtree";
  }
  return null;
}

export function refuseUnsafeQwebViewBlockText(
  blocks: Array<{ text?: string; kind?: string; type?: string }> | null | undefined,
): string | null {
  if (!blocks) return null;
  for (const block of blocks) {
    const text = block.text;
    if (typeof text === "string" && text && BLOCK_QWEB_RE.test(text)) {
      return (
        "Unsafe QWeb refused: block text must not contain QWeb " +
        "directives or template markers"
      );
    }
  }
  return null;
}

/** Combined save gate for a general QWeb view draft. */
export function refuseUnsafeQwebViewSave(input: {
  arch?: string | null;
  blocks?: Array<{ text?: string; kind?: string; type?: string }> | null;
  allowExistingTCalls?: Iterable<string> | null;
  inheritXpath?: string | null;
  inheritPosition?: string | null;
}): string | null {
  const blockErr = refuseUnsafeQwebViewBlockText(input.blocks);
  if (blockErr) return blockErr;
  if (input.arch) {
    const archErr = refuseUnsafeQwebViewArch(input.arch, {
      allowExistingTCalls: input.allowExistingTCalls,
    });
    if (archErr) return archErr;
  }
  if (input.inheritXpath && input.inheritPosition) {
    const rootErr = refuseRootReplace(input.inheritXpath, input.inheritPosition);
    if (rootErr) return rootErr;
  }
  return null;
}

/** Preview-only sanitize: strip script / on* / javascript: — save still gated. */
export function sanitizeQwebArchForPreview(arch: string): string {
  if (!arch) return "";
  return arch
    .replace(/<\s*script\b[\s\S]*?<\/\s*script\s*>/gi, "")
    .replace(/\son[a-z]+\s*=\s*(['"])[\s\S]*?\1/gi, "")
    .replace(/(href|src)\s*=\s*(['"])\s*javascript:[\s\S]*?\2/gi, '$1="#"')
    .replace(/\bt-field\s*=\s*(['"])(.*?)\1/gi, (_m, _q, field) => {
      const label = String(field || "").replace(/^doc\./, "");
      return `data-qweb-field="${label}" class="qweb-field-chip"`;
    });
}
