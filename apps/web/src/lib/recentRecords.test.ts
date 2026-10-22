import { describe, expect, it } from "vitest";
import { pushRecent, readRecent } from "./recentRecords";

describe("recent records (touch 143)", () => {
  it("newest first, no duplicates, capped", () => {
    pushRecent("c", { model: "res.partner", id: 1, name: "A" });
    pushRecent("c", { model: "res.partner", id: 2, name: "B" });
    pushRecent("c", { model: "res.partner", id: 1, name: "A" });
    expect(readRecent("c").map((r) => r.id)).toEqual([1, 2]);
    for (let i = 0; i < 30; i++) pushRecent("c", { model: "m", id: 100 + i, name: "x" }, 5);
    expect(readRecent("c")).toHaveLength(5);
  });
});
