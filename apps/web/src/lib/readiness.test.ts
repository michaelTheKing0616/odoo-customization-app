import { describe, expect, it } from "vitest";
import { dueIntro, recordDay } from "./readiness";

describe("readiness (touch 128)", () => {
  it("nothing on day one", () => {
    expect(dueIntro(recordDay({ days: [], shown: [] }, "2026-10-01"))).toBeNull();
  });
  it("density after three active days, once", () => {
    const st = { days: ["a", "b", "c"], shown: [] as string[] };
    expect(dueIntro(st)?.id).toBe("density");
    expect(dueIntro({ ...st, shown: ["density"] })).toBeNull();
  });
  it("same day counts once", () => {
    expect(recordDay({ days: ["x"], shown: [] }, "x").days).toEqual(["x"]);
  });
});
