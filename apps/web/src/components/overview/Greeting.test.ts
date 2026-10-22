import { describe, expect, it } from "vitest";
import { greetingLine } from "./Greeting";

const noon = new Date("2026-10-20T11:00:00Z");
describe("93 greeting", () => {
  it("has substance", () => {
    expect(greetingLine({ name: "Tope", approvals: 2, failed: 1, now: noon })).toBe("Good afternoon, Tope. 2 approvals waiting and 1 failed job.");
    expect(greetingLine({ name: null, approvals: 0, failed: 0, now: noon })).toBe("Good afternoon. Nothing needs you right now.");
  });
  it("never greets on its own", () => {
    expect(greetingLine({ name: "Tope", approvals: null, failed: null, now: noon })).toBeNull();
  });
});
