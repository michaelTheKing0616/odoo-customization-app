import { describe, expect, it } from "vitest";
import { readSnoozes, tomorrowMorningLagos, writeSnoozes } from "./snooze";

describe("snooze", () => {
  it("next 08:00 Lagos", () => {
    expect(new Date(tomorrowMorningLagos(Date.parse("2026-10-20T13:00:00Z"))).toISOString()).toBe("2026-10-21T07:00:00.000Z");
    expect(new Date(tomorrowMorningLagos(Date.parse("2026-10-20T05:00:00Z"))).toISOString()).toBe("2026-10-20T07:00:00.000Z");
  });
  it("drops expired snoozes", () => {
    writeSnoozes({ a: 10, b: 9e15 });
    expect(Object.keys(readSnoozes(100))).toEqual(["b"]);
  });
});
