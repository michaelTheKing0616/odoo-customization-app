import { describe, expect, it } from "vitest";
import { lineFor } from "./TransitMap";

describe("lineFor (touch 58)", () => {
  it("places steps on the right system line", () => {
    expect(lineFor("webhook received")).toBe("app");
    expect(lineFor("map fields")).toBe("ingenium");
    expect(lineFor("push")).toBe("odoo");
  });
});
