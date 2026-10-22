import { describe, expect, it } from "vitest";
import {
  compileMailBodyBlocks,
  defaultMailBlocks,
  tryParseMailBodyBlocks,
} from "./mailBodyBlocks";

describe("mailBodyBlocks", () => {
  it("compiles heading / paragraph / field to HTML", () => {
    const html = compileMailBodyBlocks([
      { id: "1", type: "heading", text: "Hello <b>", level: 2 },
      { id: "2", type: "paragraph", text: "Line & more" },
      { id: "3", type: "field", field: "name" },
    ]);
    expect(html).toContain("<h2>Hello &lt;b&gt;</h2>");
    expect(html).toContain("<p>Line &amp; more</p>");
    expect(html).toContain("{{ object.name }}");
  });

  it("round-trips simple bodies", () => {
    const blocks = defaultMailBlocks("Welcome");
    const html = compileMailBodyBlocks(blocks);
    const parsed = tryParseMailBodyBlocks(html);
    expect(parsed).not.toBeNull();
    expect(parsed!.map((b) => b.type)).toEqual([
      "heading",
      "paragraph",
      "field",
    ]);
  });

  it("refuses complex HTML (tables) — source tab path", () => {
    expect(tryParseMailBodyBlocks("<table><tr><td>x</td></tr></table>")).toBeNull();
  });
});
