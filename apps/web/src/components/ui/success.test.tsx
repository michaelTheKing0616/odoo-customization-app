import { describe, expect, it, vi } from "vitest";
vi.mock("sonner", () => ({ toast: { success: vi.fn() } }));
vi.mock("@/components/brand/BrandMark", () => ({ celebrateKeystone: vi.fn() }));
import { markSuccess } from "./success";

describe("70 success sized to the stakes", () => {
  it("first time lands the keystone, then a plain check", () => {
    localStorage.removeItem("ingenium.first.t");
    expect(markSuccess({ title: "Live", firstKey: "t", summary: ["a"] })).toBe("first");
    expect(markSuccess({ title: "Live", firstKey: "t" })).toBe("small");
    expect(markSuccess({ title: "Saved" })).toBe("small");
  });
});
