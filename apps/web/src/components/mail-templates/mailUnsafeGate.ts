/**
 * DOC-MAIL — mail body/subject gate in the PDF-05 family.
 * Reuses reportUnsafeGate (client mirror of qweb_unsafe_gate) for script /
 * t-raw / t-out / XXE / t-call. Adds mail-HTML honesty: no freeform invent,
 * no event-handler injection. Jinja `{{ object.field }}` is the Odoo mail idiom
 * and is allowed; unknown fields are refused when a grounded schema is supplied.
 */

import {
  archHasXxe,
  refuseUnsafeQwebArch,
} from "@/components/reports/reportUnsafeGate";

const EVENT_ATTR_RE = /\bon[a-z]+\s*=/i;
const JS_URL_RE = /(?:href|src)\s*=\s*(['"])\s*javascript:/i;
const DATA_HTML_RE = /(?:href|src)\s*=\s*(['"])\s*data:\s*text\/html/i;

/** Return a human refusal message, or null when the HTML is allowed. */
export function refuseUnsafeMailHtml(
  html: string,
  opts?: { knownFields?: Iterable<string> | null },
): string | null {
  if (!html) return null;

  // Same family as PDF-05 report arch gate (authoritative patterns).
  const qwebErr = refuseUnsafeQwebArch(html);
  if (qwebErr) {
    return qwebErr.replace(/report templates/g, "mail templates");
  }
  if (archHasXxe(html)) {
    return "Unsafe mail HTML refused: XML external entities (DOCTYPE / ENTITY) are not allowed";
  }
  if (EVENT_ATTR_RE.test(html)) {
    return "Unsafe mail HTML refused: inline event handlers (on*) are not allowed";
  }
  if (JS_URL_RE.test(html)) {
    return "Unsafe mail HTML refused: javascript: URLs are not allowed";
  }
  if (DATA_HTML_RE.test(html)) {
    return "Unsafe mail HTML refused: data:text/html URLs are not allowed";
  }

  const known = opts?.knownFields
    ? opts.knownFields instanceof Set
      ? opts.knownFields
      : new Set(opts.knownFields)
    : null;
  if (known) {
    const groundErr = refuseUngroundedMailPlaceholders(html, known);
    if (groundErr) return groundErr;
  }
  return null;
}

export function refuseUnsafeMailSubject(
  subject: string,
  opts?: { knownFields?: Iterable<string> | null },
): string | null {
  if (!subject) return null;
  if (/<\s*script\b/i.test(subject)) {
    return "Unsafe mail subject refused: <script> is not allowed";
  }
  if (archHasXxe(subject)) {
    return "Unsafe mail subject refused: XML external entities are not allowed";
  }
  const known = opts?.knownFields
    ? opts.knownFields instanceof Set
      ? opts.knownFields
      : new Set(opts.knownFields)
    : null;
  if (known) {
    return refuseUngroundedMailPlaceholders(subject, known);
  }
  return null;
}

/** Combined create/save gate for a mail template draft. */
export function refuseUnsafeMailTemplate(input: {
  subject?: string | null;
  body_html?: string | null;
  knownFields?: Iterable<string> | null;
}): string | null {
  const subErr = refuseUnsafeMailSubject(input.subject || "", {
    knownFields: input.knownFields,
  });
  if (subErr) return subErr;
  return refuseUnsafeMailHtml(input.body_html || "", {
    knownFields: input.knownFields,
  });
}

/** Extract object.* field names from Jinja / legacy ${} placeholders. */
export function collectMailPlaceholderFields(text: string): string[] {
  const found: string[] = [];
  const jinja = /\{\{\s*object\.([a-zA-Z_][\w.]*)/g;
  const legacy = /\$\{\s*object\.([a-zA-Z_][\w.]*)/g;
  let m: RegExpExecArray | null;
  while ((m = jinja.exec(text)) !== null) {
    found.push(m[1].split(".")[0]);
  }
  while ((m = legacy.exec(text)) !== null) {
    found.push(m[1].split(".")[0]);
  }
  return found;
}

export function refuseUngroundedMailPlaceholders(
  text: string,
  knownFields: Set<string> | Iterable<string>,
): string | null {
  const known = knownFields instanceof Set ? knownFields : new Set(knownFields);
  for (const field of collectMailPlaceholderFields(text)) {
    if (!known.has(field)) {
      return (
        `Unsafe mail template refused: unknown field '${field}' — ` +
        "pick a grounded field from the live schema (fields_get)"
      );
    }
  }
  return null;
}

/** Preview-only strip — never a substitute for the refuse gate on save. */
export function sanitizeMailHtmlForPreview(html: string): string {
  if (!html) return "";
  let out = html;
  out = out.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, "");
  out = out.replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, "");
  out = out.replace(/<(iframe|object|embed|link|meta)\b[^>]*>/gi, "");
  out = out.replace(/\son[a-z]+\s*=\s*(['"])[\s\S]*?\1/gi, "");
  out = out.replace(/\son[a-z]+\s*=\s*[^\s>]+/gi, "");
  out = out.replace(
    /(href|src)\s*=\s*(['"])\s*javascript:[\s\S]*?\2/gi,
    '$1="#"',
  );
  // Visual chips for placeholders (operate density, teal accent).
  out = out.replace(
    /\{\{\s*([^}]+?)\s*\}\}/g,
    '<span class="mail-ph" data-mail-ph="$1">{{ $1 }}</span>',
  );
  out = out.replace(
    /\$\{\s*([^}]+?)\s*\}/g,
    '<span class="mail-ph" data-mail-ph="$1">${$1}</span>',
  );
  return out;
}

export function formatMailPlaceholder(field: string): string {
  const name = (field || "").trim();
  if (!name) return "";
  return `{{ object.${name} }}`;
}
