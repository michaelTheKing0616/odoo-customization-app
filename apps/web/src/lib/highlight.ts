import { refractor } from "refractor";
import { toHtml } from "hast-util-to-html";

export type HighlightLanguage = "xml" | "json" | "python" | "text";

const LANG_MAP: Record<HighlightLanguage, string | null> = {
  xml: "markup",
  json: "json",
  python: "python",
  text: null,
};

/** Syntax-highlight code via refractor; falls back to escaped plain text. */
export function highlightCode(code: string, language: HighlightLanguage): string {
  const lang = LANG_MAP[language];
  if (!lang) {
    return escapeHtml(code);
  }
  try {
    const tree = refractor.highlight(code, lang);
    return toHtml(tree);
  } catch {
    return escapeHtml(code);
  }
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
