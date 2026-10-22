/**
 * Enforces the plain-word term card (FEATURE_AUDIT Tope addition 1): any on-screen JSX text that uses a
 * mapped plain label (MAPPED_LABELS) must sit inside <Term>, so hover/focus shows Odoo's own term.
 */
import fs from "node:fs";
import path from "node:path";
import ts from "typescript";
import { describe, expect, it } from "vitest";
import { MAPPED_LABELS, TERMS } from "@/lib/terms";

const ROOT = path.resolve(__dirname, "..");
const RE = new RegExp(`\\b(${Object.keys(MAPPED_LABELS).join("|")})s?\\b`, "i");

function files(dir: string, out: string[] = []): string[] {
  for (const f of fs.readdirSync(dir)) {
    const p = path.join(dir, f);
    if (fs.statSync(p).isDirectory()) {
      if (!/node_modules|__tests__|^e2e$/.test(f)) files(p, out);
    } else if (p.endsWith(".tsx") && !p.endsWith(".test.tsx")) out.push(p);
  }
  return out;
}

// Inside a button or link the card would nest one interactive element in another, so the label stays plain there.
const INTERACTIVE = /^(button|Button|a|Link|option|summary|DropdownMenuItem|MenuItem|Tab|TabsTrigger)$/;

function underTerm(n: ts.Node): boolean {
  for (let x = n.parent; x; x = x.parent) {
    if (ts.isJsxElement(x) && (x.openingElement.tagName.getText() === "Term" || INTERACTIVE.test(x.openingElement.tagName.getText()))) return true;
  }
  return false;
}

describe("term card guard", () => {
  it("every mapped label points at a glossary entry", () => {
    for (const tech of Object.values(MAPPED_LABELS)) expect(TERMS[tech], tech).toBeDefined();
  });

  it("no mapped plain label renders without its term card", () => {
    const misses: string[] = [];
    for (const p of files(ROOT)) {
      const src = ts.createSourceFile(p, fs.readFileSync(p, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
      const visit = (n: ts.Node) => {
        if (ts.isJsxText(n) && RE.test(n.getText()) && !underTerm(n)) {
          misses.push(`${path.relative(ROOT, p)}:${src.getLineAndCharacterOfPosition(n.getStart()).line + 1} ${n.getText().trim().slice(0, 60)}`);
        }
        ts.forEachChild(n, visit);
      };
      visit(src);
    }
    expect(misses, "Wrap these in <Term tech=…>:\n" + misses.join("\n")).toEqual([]);
  });
});
