import { describe, expect, it } from "vitest";
import { stakesFor, stakesLine } from "./stakes";

describe("stakes (touch 97)", () => {
  it("high only for a risky change on Live", () => {
    expect(stakesFor({ danger: true, environment: "Live", certain: true })).toBe("high");
    expect(stakesFor({ danger: false, environment: "Live", certain: true })).toBe("medium");
    expect(stakesFor({ danger: false, environment: "Test copy", certain: true })).toBe("low");
  });
  it("a guessed test copy is not treated as safe", () => {
    expect(stakesFor({ danger: false, environment: "Test copy", certain: false })).toBe("medium");
  });
  it("light wording only when low", () => {
    expect(stakesLine("low")).toMatch(/safe to try/);
    expect(stakesLine("high")).toMatch(/live Odoo/);
  });
});
