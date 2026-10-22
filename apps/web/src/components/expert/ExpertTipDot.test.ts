import { describe, expect, it, vi } from "vitest";
vi.mock("@/lib/api", () => ({ api: {} }));
import { hasPageTip } from "./ExpertBubble";

describe("hasPageTip (touch 110)", () => {
  it("no dot for the generic pair", () => {
    expect(hasPageTip([{ id: "modules" }, { id: "security" }])).toBe(false);
    expect(hasPageTip(undefined)).toBe(false);
  });
  it("dot when a page or model prompt exists", () => {
    expect(hasPageTip([{ id: "trigger" }])).toBe(true);
  });
});
