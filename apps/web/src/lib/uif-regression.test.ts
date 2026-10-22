import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

// D1 (Config Suite spec 3.1): the old tool pages are redirects into the suite now.
describe("old tool routes redirect into the Configuration Suite (D1)", () => {
  const cases: Array<[string, string]> = [
    ["bulk-suite", '"change"'],
    ["cron-manager", '"upkeep/schedules"'],
    ["housekeeping", '"upkeep/files"'],
    ["expert", '"ask"'],
  ];
  for (const [route, target] of cases) {
    it(`${route} redirects to suite ${target}`, () => {
      const src = fs.readFileSync(path.join(process.cwd(), `src/app/connections/[id]/${route}/page.tsx`), "utf8");
      expect(src).toContain("redirectIntoSuite");
      expect(src).toContain(target);
    });
  }
});
