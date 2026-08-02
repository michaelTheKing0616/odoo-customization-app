import { describe, expect, it } from "vitest";
import {
  parseSelectionInput,
  selectionRowsToString,
} from "./SelectionEditor";
import { domainRulesToString, parseDomainString } from "./DomainBuilder";

describe("SelectionEditor serializers", () => {
  it("builds Odoo selection string", () => {
    expect(
      selectionRowsToString([
        { value: "a", label: "A" },
        { value: "b", label: "B" },
      ]),
    ).toBe('[("a","A"),("b","B")]');
  });

  it("parses value,Label lines", () => {
    expect(parseSelectionInput("draft,Draft\ndone,Done")).toEqual([
      { value: "draft", label: "Draft" },
      { value: "done", label: "Done" },
    ]);
  });
});

describe("DomainBuilder serializers", () => {
  it("builds AND domain", () => {
    expect(
      domainRulesToString([
        { field: "x_returned", op: "=", value: "True" },
        { field: "x_name", op: "ilike", value: "loan" },
      ]),
    ).toBe('[("x_returned", "=", True), ("x_name", "ilike", "loan")]');
  });

  it("parses simple domain", () => {
    const rules = parseDomainString("[('x_returned', '=', True)]");
    expect(rules[0].field).toBe("x_returned");
    expect(rules[0].op).toBe("=");
  });
});
