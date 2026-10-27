/**
 * F1-VISUAL-REG. Handover §5.14 L713.
 * No Playwright visual-regression harness is in the repo. UI-5.14-AC stays Open.
 * it.fails keeps the default web suite collectable until a later build card adds it.
 */
// @vitest-environment node
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const WEB = join(__dirname, "../..");

function textsIn(dir: string, namePattern: RegExp): string[] {
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter((name) => namePattern.test(name))
    .map((name) => readFileSync(join(dir, name), "utf8"));
}

describe("F1-VISUAL-REG", () => {
  it.fails(
    "UI-5.14-AC: Playwright snapshots for every route, with a pixel threshold that needs an approved update",
    () => {
      const configs = textsIn(WEB, /^playwright.*\.ts$/);
      const specs = textsIn(join(WEB, "e2e"), /\.spec\.ts$/);
      expect(configs.some((text) => text.includes("maxDiffPixel"))).toBe(true);
      expect(specs.some((text) => text.includes("toHaveScreenshot"))).toBe(true);
    },
  );
});
