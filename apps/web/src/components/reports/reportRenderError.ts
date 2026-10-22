/**
 * PDF-06 / UI-S-17 — surface QWeb render failures with a template line when present.
 * Odoo / wkhtmltopdf / QWeb traces often embed "line N" or ", line N,".
 */

export type QwebRenderErrorInfo = {
  /** Original message, trimmed. */
  message: string;
  /** 1-based template / source line when detectable. */
  templateLine: number | null;
  /** Short user-facing summary (includes line when known). */
  summary: string;
};

const LINE_PATTERNS: RegExp[] = [
  /\bline\s+(\d+)\b/i,
  /,\s*line\s+(\d+)\b/i,
  /:\s*(\d+)\s*:\s*/, // path:12: style
  /\bat\s+line\s+(\d+)\b/i,
  /template.*?\bline\s+(\d+)/i,
];

export function parseQwebRenderError(raw: string): QwebRenderErrorInfo {
  const message = (raw || "").trim() || "QWeb render failed";
  let templateLine: number | null = null;
  for (const re of LINE_PATTERNS) {
    const m = message.match(re);
    if (m?.[1]) {
      const n = Number(m[1]);
      if (Number.isFinite(n) && n > 0 && n < 100_000) {
        templateLine = n;
        break;
      }
    }
  }
  const summary =
    templateLine != null
      ? `QWeb render error at template line ${templateLine}`
      : "QWeb render error";
  return { message, templateLine, summary };
}

/** One-line display for ErrorNotice / designer alert. */
export function formatQwebRenderErrorDisplay(raw: string): string {
  const info = parseQwebRenderError(raw);
  if (info.templateLine == null) return info.message;
  // Keep the original detail; lead with the named line for UI-S-17.
  if (/template line/i.test(info.message)) return info.message;
  return `${info.summary}: ${info.message}`;
}
