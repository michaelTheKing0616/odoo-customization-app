import { describe, expect, it } from "vitest";
import { navDirection } from "./PageMove";

describe("navDirection (touch 49)", () => {
  it("deeper, back and sideways", () => {
    expect(navDirection("/connections/a", "/connections/a/automations")).toBe("deeper");
    expect(navDirection("/connections/a/automations", "/connections/a")).toBe("back");
    expect(navDirection("/connections/a/automations", "/connections/a/bulk")).toBe("side");
  });
});
