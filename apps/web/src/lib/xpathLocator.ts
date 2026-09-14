/** Client-side locator scoring — Python `xpath_locator` remains source of truth for preview/save. */

const POSITIONAL_RE = /\[\s*(?:\d+|last\(\)|last\(\)\s*-\s*\d+)\s*\]/;
const NAME_OR_ID_RE = /\[@(?:name|id)\s*=/;
const STRING_RE = /\[@string\s*=/;
const STABLE_ROOTS = new Set(["//sheet", "//form", "//list", "//tree", "//search", "//kanban"]);

export function isPositional(expr: string): boolean {
  return POSITIONAL_RE.test(expr || "");
}

export function isFragile(expr: string): boolean {
  const raw = (expr || "").trim();
  if (!raw) return true;
  if (isPositional(raw)) return true;
  if (STRING_RE.test(raw) && !NAME_OR_ID_RE.test(raw)) return true;
  return false;
}

export function scoreLocator(expr: string): number {
  const raw = (expr || "").trim();
  if (!raw) return 0;
  let score = 10;
  if (NAME_OR_ID_RE.test(raw)) score += 50;
  if (raw.replace(/"/g, "'").includes("field[@name=")) score += 10;
  if (STRING_RE.test(raw)) score += 5;
  if (STABLE_ROOTS.has(raw)) score += 25;
  if (isPositional(raw)) score -= 45;
  if (/\/(?:group|page|div|field|sheet)\[\d+\]/.test(raw)) score -= 8;
  return score;
}

export function preferSemanticCandidates<T extends { xpath: string; score?: number }>(
  candidates: T[],
): T[] {
  return candidates
    .map((item, index) => ({ item, index }))
    .sort((a, b) => {
      const sa = a.item.score ?? scoreLocator(a.item.xpath);
      const sb = b.item.score ?? scoreLocator(b.item.xpath);
      if (sb !== sa) return sb - sa;
      return a.index - b.index;
    })
    .map((entry) => entry.item);
}

export function semanticInjectExpr(
  parentArch: string | null | undefined,
  viewType = "form",
): string {
  const vt = viewType === "tree" ? "list" : viewType;
  if (vt === "list") {
    if (parentArch && parentArch.includes("<tree") && !parentArch.includes("<list")) {
      return "//tree";
    }
    return "//list";
  }
  if (vt === "search") return "//search";
  if (vt !== "form") return `//${vt}`;
  if (!parentArch) return "//sheet";
  if (typeof DOMParser === "undefined") {
    return parentArch.includes("<sheet") ? "//sheet" : "//form";
  }
  const doc = new DOMParser().parseFromString(parentArch, "application/xml");
  if (doc.querySelector("parsererror")) {
    return parentArch.includes("<sheet") ? "//sheet" : "//form";
  }
  const groups = [...doc.getElementsByTagName("group")];
  if (groups.length) {
    const first = groups[0];
    for (const attr of ["name", "id", "string"] as const) {
      const val = first.getAttribute(attr);
      if (!val || val.includes("'")) continue;
      const expr = `//group[@${attr}='${val}']`;
      const unique = groups.filter((g) => g.getAttribute(attr) === val).length === 1;
      if (unique) return expr;
    }
    if (groups.length === 1) return "//group";
  }
  if (doc.getElementsByTagName("sheet").length) return "//sheet";
  return "//form";
}
