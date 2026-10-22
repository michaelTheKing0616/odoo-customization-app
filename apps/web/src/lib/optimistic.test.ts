import { describe, expect, it, vi } from "vitest";
import { optimistic } from "./optimistic";

describe("optimistic (touch 140)", () => {
  it("applies first and keeps it on success", async () => {
    const order: string[] = [];
    const r = await optimistic({ apply: () => order.push("apply"), commit: async () => { order.push("commit"); return 1; }, rollback: () => order.push("rollback") });
    expect(order).toEqual(["apply", "commit"]);
    expect(r).toBe(1);
  });
  it("rolls back with a message when the server refuses", async () => {
    const rollback = vi.fn(); const msg = vi.fn();
    await optimistic({ apply: () => {}, commit: async () => { throw new Error("no"); }, rollback, onRolledBack: msg, what: "the tests" });
    expect(rollback).toHaveBeenCalled();
    expect(msg).toHaveBeenCalledWith("Couldn't save the tests, so it was put back. Try again.");
  });
});
