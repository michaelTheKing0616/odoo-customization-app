import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * WCAG AA contrast (4.5:1 text) over every token fg/bg pair the UI actually uses, in light and dark:
 * 1. the semantic token pairs (text on surfaces, on-X on X, X-strong on X-subtle),
 * 2. every className in components/app that sets both bg-* and text-* (badges, chips, pills, buttons),
 * 3. every CSS rule that sets both a background and a color from tokens.
 */
const SRC = join(__dirname, "..", "..");
const read = (p: string) => readFileSync(join(SRC, p), "utf8");

type Vars = Record<string, string>;
function blocks(css: string): { sel: string; body: string }[] {
  const out: { sel: string; body: string }[] = [];
  const clean = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const re = /([^{}]+)\{([^{}]*)\}/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(clean))) out.push({ sel: m[1].trim(), body: m[2] });
  return out;
}
function declVars(body: string, into: Vars) {
  for (const d of body.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) into[d[1]] = d[2].trim();
}
const DARK = /(^|[\s,])(\.dark|html\.dark)\b/;
function themeVars(): { light: Vars; dark: Vars } {
  const light: Vars = {}, darkOnly: Vars = {};
  for (const f of ["styles/globals/tokens.css", "styles/globals/theme.css"]) {
    for (const b of blocks(read(f))) {
      if (b.sel.startsWith("@")) continue;
      if (DARK.test(b.sel)) declVars(b.body, darkOnly);
      else if (/(:root|^html|@theme)/.test(b.sel) || b.sel === "") declVars(b.body, light);
    }
  }
  // @theme block (tailwind) is parsed above when written as "@theme {" -> sel "@theme"; include it explicitly
  for (const b of blocks(read("styles/globals/theme.css"))) if (b.sel.includes("@theme")) declVars(b.body, light);
  return { light, dark: { ...light, ...darkOnly } };
}

type RGB = [number, number, number];
function parseColor(v: string): RGB | null {
  v = v.trim().toLowerCase();
  if (v === "white") return [255, 255, 255];
  if (v === "black") return [0, 0, 0];
  let m = v.match(/^#([0-9a-f]{3,8})$/);
  if (m) {
    let h = m[1];
    if (h.length === 3 || h.length === 4) h = h.slice(0, 3).split("").map((c) => c + c).join("");
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
  }
  m = v.match(/^rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)/);
  if (m) return [Number(m[1]), Number(m[2]), Number(m[3])];
  return null;
}
function resolve(vars: Vars, v: string, depth = 0): RGB | null {
  if (depth > 12) return null;
  const m = v.trim().match(/^var\((--[\w-]+)(?:\s*,\s*([^)]+))?\)$/);
  if (m) return vars[m[1]] !== undefined ? resolve(vars, vars[m[1]], depth + 1) : m[2] ? resolve(vars, m[2], depth + 1) : null;
  return parseColor(v);
}
const lum = ([r, g, b]: RGB) => {
  const f = (c: number) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
};
export const ratio = (a: RGB, b: RGB) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
const blend = (fg: RGB, bg: RGB, a: number): RGB => [0, 1, 2].map((i) => Math.round(fg[i] * a + bg[i] * (1 - a))) as RGB;

function walk(dir: string, ext: RegExp, out: string[] = []): string[] {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) walk(p, ext, out);
    else if (ext.test(p) && !p.includes(".test.")) out.push(p);
  }
  return out;
}

const TEXT = ["ink", "muted", "accent", "success", "warning", "danger", "info", "success-strong", "warning-strong", "danger-strong", "info-strong"];
const SURF = ["surface", "surface-raised", "surface-muted", "background"];
function tokenPairs(): [string, string, string][] {
  const pairs: [string, string, string][] = [];
  for (const t of TEXT) for (const s of SURF) pairs.push([`--${t}`, `--${s}`, `token ${t} on ${s}`]);
  pairs.push(["--on-accent", "--accent", "on-accent on accent"], ["--on-brand", "--brand", "on-brand on brand"]);
  for (const k of ["success", "warning", "danger", "info"]) pairs.push([`--${k}-strong`, `--${k}-subtle`, `${k}-strong on ${k}-subtle`]);
  pairs.push(["--accent", "--accent-subtle", "accent on accent-subtle"], ["--ink", "--accent-subtle", "ink on accent-subtle"]);
  return pairs;
}

function classPairs(): [string, string, string, number][] {
  const out: [string, string, string, number][] = [];
  for (const f of [...walk(join(SRC, "components"), /\.tsx$/), ...walk(join(SRC, "app"), /\.tsx$/)]) {
    for (const lit of readFileSync(f, "utf8").matchAll(/["'`]([^"'`\n]*\bbg-[^"'`\n]*)["'`]/g)) {
      const toks = lit[1].split(/\s+/).filter((t) => !t.includes(":"));
      const bg = toks.map((t) => t.match(/^bg-([a-z][\w-]*?)(?:\/(\d+))?$/)).find(Boolean);
      const tx = toks.map((t) => t.match(/^text-([a-z][\w-]*)$/)).find(Boolean);
      if (!bg || !tx) continue;
      const lit2 = (k: string) => (k === "white" ? "#ffffff" : k === "black" ? "#000000" : `--color-${k}`);
      out.push([lit2(tx[1]), lit2(bg[1]), `${f.replace(SRC + "/", "")}: "${bg[0]} ${tx[0]}"`, bg[2] ? Number(bg[2]) / 100 : 1]);
    }
  }
  return out;
}

type CssPair = [string, string, string, Vars, Vars, string | null];
function cssPairs(): CssPair[] {
  const out: CssPair[] = [];
  // Token colours, plus literal hex / rgb() / white / black, so hard-coded fills are judged too.
  const COL = String.raw`(var\(--[\w-]+(?:,[^)]*\)?)?\)|#[0-9a-fA-F]{3,8}|rgba?\([^)]*\)|white|black)`;
  const BG = new RegExp(String.raw`background(?:-color)?\s*:\s*${COL}\s*(?:!important)?;`);
  const FG = new RegExp(String.raw`(?:^|[;\s])color\s*:\s*${COL}\s*(?:!important)?;`);
  for (const f of walk(join(SRC, "styles"), /\.css$/).concat(walk(join(SRC, "components"), /\.css$/))) {
    const bs = blocks(readFileSync(f, "utf8")).filter((b) => !b.sel.startsWith("@"));
    for (const b of bs) {
      const bg = b.body.match(BG), fg = b.body.match(FG);
      if (!bg || !fg) continue;
      // A see-through fill sits on its scope's own background when the scope root sets one.
      const root = b.sel.match(/^\.[\w-]+/)?.[0];
      const rootBlock = root ? bs.find((x) => x.sel === root) : undefined;
      // `--contrast-on: <colour>;` in a rule names what a see-through fill really sits on (e.g. a dark bar).
      const hint = b.body.match(/--contrast-on:\s*([^;]+);/)?.[1].trim() ?? null;
      const rootBg = hint ?? rootBlock?.body.match(BG)?.[1] ?? null;
      // Custom properties the scope root (e.g. a dark chrome) and the rule itself set apply to the rule;
      // in dark, so do the root's `.dark <root>` overrides.
      const local: Vars = {}, localDark: Vars = {};
      if (rootBlock) declVars(rootBlock.body, local);
      declVars(b.body, local);
      Object.assign(localDark, local);
      for (const x of bs) if (root && DARK.test(x.sel) && x.sel.split(",").some((p) => p.trim().replace(/^(html)?\.dark\s+/, "") === root)) declVars(x.body, localDark);
      if (b !== rootBlock) declVars(b.body, localDark);
      out.push([fg[1], bg[1], `${f.replace(SRC + "/", "")} ${b.sel.slice(0, 60)}`, local, localDark, rootBg]);
    }
  }
  return out;
}

const LIGHT_BG = 0.4, DARK_FG = 0.2;

describe("WCAG AA contrast, light and dark", () => {
  it("every used fg/bg pair reaches 4.5:1, and light backgrounds carry dark text", () => {
    const { light, dark } = themeVars();
    const fails: string[] = [];
    for (const [theme, vars] of [["light", light], ["dark", dark]] as const) {
      const baseSurface = resolve(vars, "var(--surface)")!;
      const check = (fgV: string, bgV: string, label: string, alpha = 1, local: Vars = {}, under: string | null = null) => {
        const v: Vars = { ...vars, ...local };
        const fg = resolve(v, fgV.startsWith("--") ? `var(${fgV})` : fgV);
        let bg = resolve(v, bgV.startsWith("--") ? `var(${bgV})` : bgV);
        const surface = (under && under !== bgV && resolve(v, under)) || baseSurface;
        if (!fg || !bg) return; // non-token or transparent colours are not judged here
        if (alpha < 1) bg = blend(bg, surface, alpha);
        const aOf = (v: string) => { const m = v.match(/^rgba?\([^)]*?[,/]\s*([\d.]+%?)\s*\)$/); return m ? (m[1].endsWith("%") ? parseFloat(m[1]) / 100 : parseFloat(m[1])) : 1; };
        if (aOf(bgV) < 1) bg = blend(bg, surface, aOf(bgV));
        const fgA = aOf(fgV);
        const fgSolid = fgA < 1 ? blend(fg, bg, fgA) : fg;
        const r = ratio(fgSolid, bg);
        if (r < 4.5) fails.push(`${theme}: ${label} = ${r.toFixed(2)}`);
        // Polarity rule (Tope): a light-ish background (luminance > 0.4) always carries dark text (luminance < 0.2).
        if (lum(bg) > LIGHT_BG && lum(fgSolid) >= DARK_FG) fails.push(`${theme}: ${label} light background needs dark text (bg ${lum(bg).toFixed(2)}, fg ${lum(fgSolid).toFixed(2)})`);
      };
      for (const [f, b, l] of tokenPairs()) check(f, b, l);
      for (const [f, b, l, a] of classPairs()) check(f, b, l, a);
      for (const [f, b, l, loc, locDark, under] of cssPairs()) check(f, b, l, 1, theme === "dark" ? locDark : loc, under);
    }
    expect([...new Set(fails)]).toEqual([]);
  });
});
