import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// A2 — one page frame: every screen title inside a connection shows the shared meta row
// (database, Odoo version, Writes On/Off). Error/not-found pages and the Odoo form preview are exempt.
const EXEMPT = [/error\.tsx$/, /not-found\.tsx$/, /odoo-preview\//, /\.test\.tsx$/];

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (p.endsWith(".tsx")) out.push(p);
  }
  return out;
}

describe("A2 page frame guard", () => {
  it("every screen title carries the shared frame row", () => {
    const root = join(__dirname, "..", "..");
    const files = [...walk(join(root, "app", "connections")), ...walk(join(root, "components"))];
    const missing = files.filter((f) => {
      if (EXEMPT.some((r) => r.test(f.replaceAll("\\", "/")))) return false;
      const s = readFileSync(f, "utf8");
      return s.includes("<h1") && !/FrameMeta|PageHeader|OperateStudioChrome/.test(s);
    });
    expect(missing).toEqual([]);
  });
});
