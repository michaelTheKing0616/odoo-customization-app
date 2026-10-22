import { describe, expect, it } from "vitest";
import {
  compileInheritFragment,
  compileQwebViewBlocks,
  defaultQwebViewBlocks,
  tryParseQwebViewBlocks,
} from "./qwebViewBlocks";

describe("qwebViewBlocks DOC-QWEB", () => {
  it("compiles grounded blocks to a page fragment", () => {
    const arch = compileQwebViewBlocks(defaultQwebViewBlocks("Hello"));
    expect(arch).toContain('<div class="page">');
    expect(arch).toContain("<h2>Hello</h2>");
    expect(arch).toContain('t-field="doc.display_name"');
  });

  it("round-trips Ingenium-authored arches", () => {
    const blocks = defaultQwebViewBlocks("Invoice");
    const arch = compileQwebViewBlocks(blocks);
    const parsed = tryParseQwebViewBlocks(arch);
    expect(parsed).not.toBeNull();
    expect(parsed!.map((b) => b.kind)).toEqual(["heading", "paragraph", "field"]);
    expect(parsed![0].kind === "heading" && parsed![0].text).toBe("Invoice");
  });

  it("returns null for foreign bodies", () => {
    expect(tryParseQwebViewBlocks("<table><tr><td>x</td></tr></table>")).toBeNull();
    expect(
      tryParseQwebViewBlocks('<data><xpath expr="//div" position="inside"><p>x</p></xpath></data>'),
    ).toBeNull();
  });

  it("compiles inherit fragments without escaping xpath quotes", () => {
    const frag = compileInheritFragment(defaultQwebViewBlocks("X"), {
      xpath: "//div[hasclass('page')]",
      position: "inside",
    });
    expect(frag).toContain("hasclass('page')");
    expect(frag).not.toContain("&#x27;");
    expect(frag).toContain("<data>");
  });
});
