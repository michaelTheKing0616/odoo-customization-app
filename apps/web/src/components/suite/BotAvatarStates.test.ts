import { describe, expect, it } from "vitest";
import { canMove } from "./BotAvatar";

describe("bot state machine (touch 104)", () => {
  it("allows the honest path and blocks jumps", () => {
    expect(canMove("idle", "thinking")).toBe(true);
    expect(canMove("thinking", "working")).toBe(true);
    expect(canMove("working", "done")).toBe(true);
    expect(canMove("idle", "done")).toBe(false);
    expect(canMove("needs_you", "done")).toBe(false);
  });
});
