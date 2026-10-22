/**
 * UI-S-12 canvas states: view XML invalid (line + reason), inherit conflict,
 * preview stale. Pure helpers so the page, the harness and tests share one
 * classification. Copy is what / why / next, no em dashes (playbook §9).
 */

export type DesignerCanvasStateKind = "xml-invalid" | "inherit-conflict" | "preview-stale";

export type DesignerCanvasStateAction = {
  label: string;
  onClick: () => void;
};

export type DesignerCanvasState =
  | { kind: "xml-invalid"; line: number | null; reason: string; action?: DesignerCanvasStateAction }
  | {
      kind: "inherit-conflict";
      locator: string | null;
      reason: string;
      action?: DesignerCanvasStateAction;
    }
  | { kind: "preview-stale"; action?: DesignerCanvasStateAction };

export type DesignerErrorState = Exclude<DesignerCanvasState, { kind: "preview-stale" }>;

const INHERIT_CONFLICT = /cannot be located in parent view|cannot be located in the parent view/i;

const XML_INVALID =
  /XMLSyntaxError|Opening and ending tag mismatch|not well-formed|Premature end of data|Extra content at the end|StartTag:|EndTag:|Couldn't find end of Start Tag|Invalid view definition|Error while validating view|Invalid XML|xmlParse/i;

const MAX_REASON = 180;

/** Prefer lxml's "line N, column M", then Odoo's view error context, then any "line N". */
export function viewErrorLine(message: string): number | null {
  const patterns = [
    /line\s+(\d+),\s*column\s+\d+/i,
    /['"]line['"]\s*:\s*(\d+)/i,
    /\bline\s+(\d+)\b/i,
  ];
  for (const re of patterns) {
    const m = message.match(re);
    if (m) {
      const n = Number(m[1]);
      if (Number.isFinite(n) && n > 0) return n;
    }
  }
  return null;
}

function cleanReason(message: string): string {
  const firstUseful =
    message
      .split(/\r?\n/)
      .map((l) => l.trim())
      .find((l) => l && !/^error while validating view near:?$/i.test(l) && !/^traceback/i.test(l)) ??
    message.trim();
  let reason = firstUseful
    .replace(/^(lxml\.etree\.)?XMLSyntaxError:\s*/i, "")
    .replace(/^ValidationError:\s*/i, "")
    .replace(/^Invalid view definition:?\s*/i, "")
    .replace(/\s*\(<string>,\s*line\s+\d+\)\s*$/i, "")
    .replace(/,?\s*line\s+\d+,\s*column\s+\d+\s*$/i, "")
    .replace(/\s+/g, " ")
    .trim();
  if (!reason) reason = "Odoo rejected the view XML.";
  if (reason.length > MAX_REASON) reason = `${reason.slice(0, MAX_REASON - 1).trimEnd()}…`;
  return reason;
}

function inheritLocator(message: string): string | null {
  const element = message.match(/Element\s+['"](.+?)['"]\s+cannot be located/i);
  if (element) {
    const expr = element[1].match(/expr=(["'])(.+?)\1/);
    return expr ? expr[2] : element[1];
  }
  const expr = message.match(/expr=(["'])(.+?)\1/);
  return expr ? expr[2] : null;
}

/** Map an API/save error to a canvas state, or null when it is some other failure. */
export function classifyDesignerError(message: string | null | undefined): DesignerErrorState | null {
  if (!message || !message.trim()) return null;
  if (INHERIT_CONFLICT.test(message)) {
    return {
      kind: "inherit-conflict",
      locator: inheritLocator(message),
      reason: cleanReason(message),
    };
  }
  if (XML_INVALID.test(message)) {
    return { kind: "xml-invalid", line: viewErrorLine(message), reason: cleanReason(message) };
  }
  return null;
}

/** Live Odoo renders the saved view; unsaved canvas edits make it stale. */
export function isPreviewStale(opts: {
  mode: "live" | "structure";
  liveAvailable: boolean;
  dirty: boolean;
}): boolean {
  return opts.mode === "live" && opts.liveAvailable && opts.dirty;
}

/**
 * Plain-language gloss for the lxml messages people actually hit when a view
 * breaks. Returns null when we have no better wording than Odoo's own.
 */
export function explainXmlReason(reason: string): string | null {
  const mismatch = reason.match(
    /Opening and ending tag mismatch:\s*([A-Za-z_][\w:-]*)\s+line\s+(\d+)\s+and\s+([A-Za-z_][\w:-]*)/i,
  );
  if (mismatch) {
    const [, open, line, close] = mismatch;
    return `The <${open}> opened on line ${line} is still open when </${close}> closes. Close the <${open}> first.`;
  }
  const premature = reason.match(/Premature end of data in tag\s+([A-Za-z_][\w:-]*)\s+line\s+(\d+)/i);
  if (premature) {
    const [, tag, line] = premature;
    return `The <${tag}> opened on line ${line} is never closed.`;
  }
  const startTag = reason.match(/Couldn't find end of Start Tag\s+([A-Za-z_][\w:-]*)(?:\s+line\s+(\d+))?/i);
  if (startTag) {
    const [, tag, line] = startTag;
    return line
      ? `The <${tag}> tag on line ${line} is missing its closing bracket.`
      : `A <${tag}> tag is missing its closing bracket.`;
  }
  if (/Extra content at the end of the document/i.test(reason)) {
    return "There is markup after the view's closing root tag. Keep everything inside one root element.";
  }
  if (/StartTag: invalid element name/i.test(reason)) {
    return "A tag name is not valid XML. Check for a stray < or a name that starts with a number.";
  }
  return null;
}

export type DesignerCanvasStateCopy = {
  tone: "danger" | "warning" | "neutral";
  title: string;
  /** Plain sentence; `code` is rendered as an inline code span after it. */
  text: string;
  code?: string | null;
  /** Short label shown before `code` ("Locator", "Odoo's message"). */
  codeLabel?: string | null;
  role: "alert" | "status";
};

export function canvasStateCopy(state: DesignerCanvasState): DesignerCanvasStateCopy {
  switch (state.kind) {
    case "xml-invalid": {
      const plain = explainXmlReason(state.reason);
      return {
        tone: "danger",
        title: state.line
          ? `The view XML has an error on line ${state.line}`
          : "The view XML has an error",
        text: plain
          ? `${plain} Fix it in Advanced, then save again.`
          : `${state.reason} Fix it in Advanced, then save again.`,
        code: plain ? state.reason : null,
        codeLabel: plain ? "Odoo's message" : null,
        role: "alert",
      };
    }
    case "inherit-conflict":
      return {
        tone: "warning",
        title: "Odoo can't find where to attach this change",
        text: state.locator
          ? "The parent view has no match for this locator. Another module may have moved or renamed it. Pick a named locator in Advanced, then save again."
          : "The parent view no longer has the element this inherit points at. Pick a named locator in Advanced, then save again.",
        code: state.locator,
        codeLabel: state.locator ? "Locator" : null,
        role: "alert",
      };
    case "preview-stale":
      return {
        tone: "neutral",
        title: "Live Odoo shows the last saved view",
        text: "Your canvas edits are not in it yet. Save to Odoo to publish them, or switch to the layout canvas to see them now.",
        role: "status",
      };
  }
}
