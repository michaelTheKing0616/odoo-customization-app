import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/** Touch 136: screen-reader messages are written like copy: say what happened to what, never a bare status word. */
const BARE = /(role="(status|alert)"|aria-live="[a-z]+")[^>]*>\s*(Updating…|Loading…?|Error|Success|Done|Saved|Failed|Saving…|Working…)\s*</;

function walk(dir: string, out: string[] = []): string[] {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (p.endsWith(".tsx") && !p.includes(".test.")) out.push(p);
  }
  return out;
}

describe("screen-reader copy (touch 136)", () => {
  it("no live region announces a bare status word", () => {
    const root = join(__dirname, "..");
    const hits = [...walk(join(root, "components")), ...walk(join(root, "app"))].filter((f) => BARE.test(readFileSync(f, "utf8")));
    expect(hits).toEqual([]);
  });
});
