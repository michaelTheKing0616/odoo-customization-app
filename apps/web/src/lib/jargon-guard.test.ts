/** FEATURE_AUDIT A3: banned internal words must not reach the screen. Extend BANNED as the sweep continues. */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const BANNED = [
  "Mutations blocked",
  "grounded fields only",
  "unsafe gate family",
  "TRUST-9",
  "sha256 required",
  'title="Philosophy"',
  "XML-RPC",
  "JSON-RPC",
];

function walk(dir: string, out: string[] = []): string[] {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(tsx?|jsx?)$/.test(n) && !/\.test\./.test(n)) out.push(p);
  }
  return out;
}

describe("jargon guard", () => {
  it("no banned internal words in UI source", () => {
    const root = join(__dirname, "..");
    const hits = walk(root).flatMap((f) => {
      const s = readFileSync(f, "utf8");
      return BANNED.filter((w) => s.includes(w)).map((w) => `${f.slice(root.length)}: ${w}`);
    });
    expect(hits).toEqual([]);
  });
});
