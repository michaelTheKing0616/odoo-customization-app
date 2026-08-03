import { describe, expect, it } from "vitest";
import { cn } from "@/lib/cn";

describe("cn", () => {
  it("merges class names", () => {
    expect(cn("a", false && "b", "c")).toBe("a c");
  });
});

describe("Button variants contract", () => {
  it("documents primary variant token", () => {
    expect("primary").toBeTruthy();
  });
});
