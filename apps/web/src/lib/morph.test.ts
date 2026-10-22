import { describe, expect, it, vi } from "vitest";
import { morphNavigate } from "./morph";

describe("morphNavigate (touch 35)", () => {
  it("falls back to plain navigation without View Transitions", () => {
    const push = vi.fn();
    morphNavigate(push, "/connections/a", document.createElement("li"));
    expect(push).toHaveBeenCalledWith("/connections/a");
  });
});
