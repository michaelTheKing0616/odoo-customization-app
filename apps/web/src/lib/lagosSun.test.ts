import { describe, expect, it } from "vitest";
import { isLagosNight, lagosSunUtcMinutes } from "./lagosSun";

describe("Lagos sun", () => {
  it("sets around 18:40 WAT in October", () => {
    const { sunset } = lagosSunUtcMinutes(new Date("2026-10-20T12:00:00Z"));
    const wat = sunset + 60;
    expect(wat).toBeGreaterThan(18 * 60 + 15);
    expect(wat).toBeLessThan(19 * 60);
  });
  it("is night at 21:00 WAT and day at noon", () => {
    expect(isLagosNight(new Date("2026-10-20T20:00:00Z"))).toBe(true);
    expect(isLagosNight(new Date("2026-10-20T11:00:00Z"))).toBe(false);
  });
});
