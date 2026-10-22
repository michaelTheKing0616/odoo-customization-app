/**
 * PDF-03 — inherit slot picker → single report.inherit anchor.
 *
 * Slot → xpath / position map (stable QWeb anchors; never `replace`):
 *   header      → //div[@class='header']  position=inside
 *   before_body → //div[@class='page']    position=before
 *   after_body  → //div[@class='page']    position=after
 *   footer      → //div[@class='footer']  position=inside
 *
 * Free-form xpath is not exposed in the default UI. The compiler emits one
 * inherit xpath for the chosen slot. RT-22 root/large replace is refused
 * client-side before save; the server `report_inherit_issues` remains the
 * authority at apply time.
 */

export type ReportInheritSlot =
  | "header"
  | "before_body"
  | "after_body"
  | "footer";

export type ReportInheritPosition = "inside" | "after" | "before" | "replace";

export type ReportInheritAnchor = {
  slot: ReportInheritSlot;
  xpath: string;
  position: Exclude<ReportInheritPosition, "replace">;
  label: string;
  hint: string;
};

/** Ordered picker entries. Positions are never `replace`. */
export const REPORT_INHERIT_SLOTS: readonly ReportInheritAnchor[] = [
  {
    slot: "header",
    xpath: "//div[@class='header']",
    position: "inside",
    label: "Header",
    hint: "Inside the external-layout header band",
  },
  {
    slot: "before_body",
    xpath: "//div[@class='page']",
    position: "before",
    label: "Before page body",
    hint: "Sibling immediately before the page container",
  },
  {
    slot: "after_body",
    xpath: "//div[@class='page']",
    position: "after",
    label: "After page body",
    hint: "Sibling immediately after the page container",
  },
  {
    slot: "footer",
    xpath: "//div[@class='footer']",
    position: "inside",
    label: "Footer",
    hint: "Inside the external-layout footer band",
  },
] as const;

const SLOT_BY_ID = Object.fromEntries(
  REPORT_INHERIT_SLOTS.map((s) => [s.slot, s]),
) as Record<ReportInheritSlot, ReportInheritAnchor>;

export const DEFAULT_INHERIT_SLOT: ReportInheritSlot = "after_body";

export function inheritAnchorForSlot(slot: ReportInheritSlot): ReportInheritAnchor {
  return SLOT_BY_ID[slot] ?? SLOT_BY_ID[DEFAULT_INHERIT_SLOT];
}

/** Reverse map xpath+position → slot when round-tripping a saved arch. */
export function slotFromXpathPosition(
  xpath: string,
  position: string,
): ReportInheritSlot | null {
  const expr = (xpath || "").trim().replace(/"/g, "'");
  const pos = (position || "").trim().toLowerCase();
  for (const entry of REPORT_INHERIT_SLOTS) {
    const entryExpr = entry.xpath.replace(/"/g, "'");
    if (entryExpr === expr && entry.position === pos) return entry.slot;
  }
  return null;
}

/** Expressions that RT-22 treats as root / large subtree (mirror of ui_ops). */
const ROOT_OR_LARGE_EXPRS = new Set([
  "/",
  "/*",
  "//",
  "//*",
  ".",
  "//.",
  "//form",
  "//form[1]",
  "//tree",
  "//list",
  "//kanban",
  "//search",
  "//sheet",
  "//notebook",
  "//t",
  "//div[@class='page']",
  '//div[@class="page"]',
  "//div[@class='article']",
  '//div[@class="article"]',
  "//div[contains(@class, 'page')]",
  "//div[contains(@class, 'article')]",
]);

const TEMPLATE_ROOT_RE =
  /^(?:\/|\/\/)t(?:\[@t-(?:name|call)=(['"])[^'"]+\1\])?$/i;
const PAGE_OR_ARTICLE_RE =
  /^\/\/div\[(?:@class=(['"])(?:page|article)\1|contains\(@class,(['"])(?:page|article)\2)\)$/i;

export function isRootOrLargeExpr(expr: string): boolean {
  const norm = (expr || "").replace(/\s+/g, "");
  if (!norm) return false;
  if (ROOT_OR_LARGE_EXPRS.has(norm) || ROOT_OR_LARGE_EXPRS.has(norm.replace(/"/g, "'"))) {
    return true;
  }
  if (TEMPLATE_ROOT_RE.test(norm) || PAGE_OR_ARTICLE_RE.test(norm)) return true;
  return false;
}

export const RT22_ROOT_REPLACE_MESSAGE =
  "xpath replaces the root or a large subtree";

/**
 * Client RT-22 gate: position `replace` on `/` or a root/large node is refused
 * before save. Non-replace positions (slot picker) always pass.
 */
export function reportInheritRootReplaceIssue(params: {
  xpath?: string | null;
  anchor?: string | null;
  position?: string | null;
}): string | null {
  const position = (params.position || "").trim().toLowerCase();
  if (position !== "replace") return null;
  const expr = (params.xpath || params.anchor || "").trim();
  if (!expr) return null;
  if (isRootOrLargeExpr(expr)) return RT22_ROOT_REPLACE_MESSAGE;
  return null;
}

export type ReportInheritOpParams = {
  base_report_key: string;
  xpath: string;
  position: Exclude<ReportInheritPosition, "replace">;
  expect_matches: 1;
  slot: ReportInheritSlot;
  arch?: string;
  model?: string;
  name?: string;
};

export type ReportInheritOp = {
  type: "report.inherit";
  params: ReportInheritOpParams;
};

export type BuildReportInheritOpInput = {
  baseReportKey: string;
  slot: ReportInheritSlot;
  /** Known report_name / report keys on the connection (fixture in tests). */
  availableReportKeys: readonly string[];
  arch?: string;
  model?: string;
  name?: string;
};

export type BuildReportInheritOpResult =
  | { ok: true; op: ReportInheritOp }
  | { ok: false; error: string };

/**
 * Emit one `report.inherit` op with exactly one anchor for the chosen slot.
 * Refuses a missing base key and any accidental root replace.
 */
export function buildReportInheritOp(
  input: BuildReportInheritOpInput,
): BuildReportInheritOpResult {
  const base = (input.baseReportKey || "").trim();
  if (!base) {
    return { ok: false, error: "Pick an existing report to extend" };
  }
  const keys = new Set(
    input.availableReportKeys.map((k) => k.trim()).filter(Boolean),
  );
  if (keys.size > 0 && !keys.has(base)) {
    return {
      ok: false,
      error: `Base report key does not exist on this connection: ${base}`,
    };
  }
  const anchor = inheritAnchorForSlot(input.slot);
  const rt22 = reportInheritRootReplaceIssue({
    xpath: anchor.xpath,
    position: anchor.position,
  });
  if (rt22) {
    return { ok: false, error: rt22 };
  }
  return {
    ok: true,
    op: {
      type: "report.inherit",
      params: {
        base_report_key: base,
        xpath: anchor.xpath,
        position: anchor.position,
        expect_matches: 1,
        slot: anchor.slot,
        ...(input.arch ? { arch: input.arch } : {}),
        ...(input.model ? { model: input.model } : {}),
        ...(input.name ? { name: input.name } : {}),
      },
    },
  };
}

/** Parse the single xpath slot out of a compiled inherit arch for round-trip. */
export function parseInheritSlotFromArch(arch: string): {
  baseReportKey: string | null;
  slot: ReportInheritSlot | null;
  xpath: string | null;
  position: string | null;
} {
  const baseMatch = arch.match(/\bt-inherit=(['"])([^'"]+)\1/i);
  // XPath values often embed the opposite quote (e.g. expr="//div[@class='page']").
  const tagMatch = arch.match(/<xpath\b([^>]*)>/i);
  let xpath: string | null = null;
  let position: string | null = null;
  if (tagMatch) {
    const attrs = tagMatch[1];
    const exprMatch = attrs.match(/\bexpr=(['"])([\s\S]*?)\1/i);
    const posMatch = attrs.match(/\bposition=(['"])([^'"]*)\1/i);
    if (exprMatch) xpath = exprMatch[2];
    if (posMatch) position = posMatch[2];
  }
  const slot =
    xpath && position ? slotFromXpathPosition(xpath, position) : null;
  return {
    baseReportKey: baseMatch?.[2] ?? null,
    slot,
    xpath,
    position,
  };
}

export type PersistedReportDesign = {
  mode: "primary" | "inherit";
  inheritSlot?: ReportInheritSlot;
  inheritBase?: string;
  blocks: unknown[];
  useExternalLayout?: boolean;
  tLang?: string;
};

export function reportDesignStorageKey(
  connectionId: string,
  reportKey: string,
): string {
  return `odoo-report-design:${connectionId}:${reportKey}`;
}

export function loadPersistedReportDesign(
  connectionId: string,
  reportKey: string,
  storage: Pick<Storage, "getItem"> = globalThis.localStorage,
): PersistedReportDesign | null {
  if (!connectionId || !reportKey || !storage) return null;
  try {
    const raw = storage.getItem(reportDesignStorageKey(connectionId, reportKey));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PersistedReportDesign;
    if (!parsed || (parsed.mode !== "primary" && parsed.mode !== "inherit")) {
      return null;
    }
    if (!Array.isArray(parsed.blocks)) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function persistReportDesign(
  connectionId: string,
  reportKey: string,
  design: PersistedReportDesign,
  storage: Pick<Storage, "setItem"> = globalThis.localStorage,
): void {
  if (!connectionId || !reportKey || !storage) return;
  try {
    storage.setItem(
      reportDesignStorageKey(connectionId, reportKey),
      JSON.stringify(design),
    );
  } catch {
    // Quota / private mode — round-trip still works from arch when possible.
  }
}
