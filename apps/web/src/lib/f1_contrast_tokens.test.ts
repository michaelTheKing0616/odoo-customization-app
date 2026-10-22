import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * F1-CONTRAST-TOKENS. Every surface token carries a paired on-* ink.
 * A fill with relative luminance above 0.18 pairs only with dark ink
 * (ink luminance at or below 0.18).
 */
const ROOT = join(__dirname, "..", "styles", "globals");
const LIGHT_FILL = 0.18;
const NOT_SURFACE = new Set(["ink", "muted", "subtle", "border-subtle", "border-strong"]);

type RGB = [number, number, number];
type Vars = Record<string, string>;

function strip(css: string): string {
  return css.replace(/\/\*[\s\S]*?\*\//g, "");
}

function blocks(css: string): { sel: string; body: string }[] {
  const out: { sel: string; body: string }[] = [];
  const re = /([^{}]+)\{([^{}]*)\}/g;
  let match: RegExpExecArray | null;
  while ((match = re.exec(css))) out.push({ sel: match[1].trim(), body: match[2] });
  return out;
}

function declVars(body: string, into: Vars) {
  for (const decl of body.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) into[decl[1]] = decl[2].trim();
}

const DARK = /(^|[\s,])(\.dark|html\.dark)\b/;

function themeVars(css: string): { light: Vars; dark: Vars } {
  const light: Vars = {};
  const darkOnly: Vars = {};
  for (const block of blocks(strip(css))) {
    if (block.sel.startsWith("@")) continue;
    if (DARK.test(block.sel)) declVars(block.body, darkOnly);
    else declVars(block.body, light);
  }
  return { light, dark: { ...light, ...darkOnly } };
}

function parseColor(value: string): RGB | null {
  const color = value.trim().toLowerCase();
  if (color === "white") return [255, 255, 255];
  if (color === "black") return [0, 0, 0];
  const match = color.match(/^#([0-9a-f]{3,8})$/);
  if (!match) return null;
  let hex = match[1];
  if (hex.length === 3 || hex.length === 4) hex = hex.slice(0, 3).split("").map((c) => c + c).join("");
  if (hex.length < 6) return null;
  return [parseInt(hex.slice(0, 2), 16), parseInt(hex.slice(2, 4), 16), parseInt(hex.slice(4, 6), 16)];
}

function resolve(vars: Vars, value: string, depth = 0): RGB | null {
  if (depth > 12) return null;
  const match = value.trim().match(/^var\((--[\w-]+)/);
  if (match) {
    const next = vars[match[1]];
    return next === undefined ? null : resolve(vars, next, depth + 1);
  }
  return parseColor(value);
}

function luminance([r, g, b]: RGB): number {
  const channel = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrastRatio(bg: RGB, fg: RGB): number {
  const [hi, lo] = [luminance(bg), luminance(fg)].sort((a, b) => b - a);
  return (hi + 0.05) / (lo + 0.05);
}

/** A fill above 0.18 luminance pairs only with dark ink. */
function allowsInk(bg: RGB, fg: RGB): boolean {
  if (luminance(bg) > LIGHT_FILL) return luminance(fg) <= LIGHT_FILL;
  return true;
}

function themeColors(css: string): Map<string, string> {
  const out = new Map<string, string>();
  for (const match of strip(css).matchAll(/--color-([\w-]+)\s*:\s*([^;]+);/g)) {
    out.set(match[1], match[2].trim());
  }
  return out;
}

function surfaces(colors: Map<string, string>): string[] {
  return [...colors.keys()].filter((name) => !name.startsWith("on-") && !NOT_SURFACE.has(name));
}

const tokens = themeVars(readFileSync(join(ROOT, "tokens.css"), "utf8"));
const colors = themeColors(readFileSync(join(ROOT, "theme.css"), "utf8"));

describe("surface on-* tokens", () => {
  it("pairs every surface token with on-* and keeps light fills on dark ink", () => {
    const names = surfaces(colors);
    expect(names.length).toBeGreaterThan(30);
    const problems: string[] = [];
    for (const name of names) {
      if (colors.get(`on-${name}`) !== `var(--on-${name})`) {
        problems.push(`theme missing --color-on-${name}`);
        continue;
      }
      for (const theme of ["light", "dark"] as const) {
        const vars = tokens[theme];
        const bgValue = colors.get(name);
        const bg = bgValue ? resolve(vars, bgValue) : null;
        const fg = resolve(vars, `var(--on-${name})`);
        if (!bg || !fg) {
          problems.push(`${theme} ${name}: unresolved`);
          continue;
        }
        if (!allowsInk(bg, fg)) {
          problems.push(
            `${theme} ${name}: bg ${luminance(bg).toFixed(3)} needs dark ink, got ${luminance(fg).toFixed(3)}`,
          );
        }
      }
    }
    expect(problems).toEqual([]);
  });

  it("rejects measured light ink on light fills", () => {
    const rejected: { bg: string; fg: string; ratio: string }[] = [
      { bg: "#f97316", fg: "#ffffff", ratio: "2.80" },
      { bg: "#fb923c", fg: "#ffffff", ratio: "2.26" },
      { bg: "#14b8a6", fg: "#ffffff", ratio: "2.49" },
      { bg: "#2dd4bf", fg: "#ffffff", ratio: "1.86" },
      { bg: "#0d9488", fg: "#ffffff", ratio: "3.74" },
      { bg: "#ccfbf1", fg: "#14b8a6", ratio: "2.21" },
      { bg: "#ccfbf1", fg: "#0d9488", ratio: "3.32" },
    ];
    for (const row of rejected) {
      const bg = parseColor(row.bg);
      const fg = parseColor(row.fg);
      if (!bg || !fg) throw new Error(`${row.fg} on ${row.bg}`);
      expect(contrastRatio(bg, fg).toFixed(2)).toBe(row.ratio);
      expect(allowsInk(bg, fg)).toBe(false);
    }
  });

  it("keeps measured pairs that pass: white on #0f766e, basalt on teal and orange", () => {
    const kept: { bg: string; fg: string; ratio: string }[] = [
      { bg: "#0f766e", fg: "#ffffff", ratio: "5.47" },
      { bg: "#2dd4bf", fg: "#1a1c21", ratio: "9.16" },
      { bg: "#f97316", fg: "#1a1c21", ratio: "6.08" },
    ];
    for (const row of kept) {
      const bg = parseColor(row.bg);
      const fg = parseColor(row.fg);
      if (!bg || !fg) throw new Error(`${row.fg} on ${row.bg}`);
      expect(contrastRatio(bg, fg).toFixed(2)).toBe(row.ratio);
      expect(allowsInk(bg, fg)).toBe(true);
    }
  });
});
