import { describe, expect, it } from "vitest";
import { asSpecBool, parseSelectionOptions, uid } from "./designer-model";

describe("designer-model", () => {
  it("asSpecBool only accepts booleans", () => {
    expect(asSpecBool(true)).toBe(true);
    expect(asSpecBool(false)).toBe(false);
    expect(asSpecBool("1")).toBe(null);
    expect(asSpecBool(null)).toBe(null);
  });

  it("parseSelectionOptions reads Odoo selection tuples", () => {
    expect(parseSelectionOptions("[('a', 'Alpha'), ('b', 'Beta')]")).toEqual([
      { value: "a", label: "Alpha" },
      { value: "b", label: "Beta" },
    ]);
  });

  it("uid prefixes ids deterministically by call order", () => {
    const a = uid("field");
    const b = uid("field");
    expect(a.startsWith("field_")).toBe(true);
    expect(b).not.toBe(a);
  });
});
