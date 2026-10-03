import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  COMMUNITY20_SAMPLE_MODULES,
  nativeMcpPresent,
} from "./odoo-native-mcp";

describe("nativeMcpPresent (mirrors odoo-client version_table)", () => {
  it("returns false for Community module lists without ai*", () => {
    expect(nativeMcpPresent(["sale", "account"])).toBe(false);
    expect(nativeMcpPresent([...COMMUNITY20_SAMPLE_MODULES])).toBe(false);
  });

  it("returns true when any module name starts with ai", () => {
    expect(nativeMcpPresent(["ai_agent"])).toBe(true);
    expect(nativeMcpPresent(["sale", "ai"])).toBe(true);
  });
});

const WEB_SRC_ROOT = path.join(process.cwd(), "src");
/** UI copy must not imply native MCP is offered on Community. */
const POSITIVE_MCP_AVAILABILITY = [
  /MCP available/i,
  /native MCP (is )?available/i,
  /Model Context Protocol (is )?available/i,
];

function collectSourceFiles(dir: string, out: string[] = []): string[] {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "node_modules") continue;
      collectSourceFiles(full, out);
    } else if (/\.(tsx?|jsx?)$/.test(entry.name) && !/\.test\.(tsx?|jsx?)$/.test(entry.name)) {
      out.push(full);
    }
  }
  return out;
}

describe("product UI does not claim native MCP availability", () => {
  it("no apps/web/src screen copy asserts MCP is available", () => {
    const hits: string[] = [];
    for (const file of collectSourceFiles(WEB_SRC_ROOT)) {
      const rel = path.relative(WEB_SRC_ROOT, file);
      const lines = fs.readFileSync(file, "utf8").split("\n");
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i]!;
        for (const re of POSITIVE_MCP_AVAILABILITY) {
          if (re.test(line)) {
            hits.push(`${rel}:${i + 1}: ${line.trim()}`);
          }
        }
      }
    }
    expect(hits, hits.join("\n")).toEqual([]);
  });
});
