import { describe, expect, it } from "vitest";
import { stonesLaid } from "./ArchDrawing";

describe("stonesLaid (touch 125)", () => {
  it("one stone per share of steps, all six when done", () => {
    expect(stonesLaid(0, 4)).toBe(0);
    expect(stonesLaid(2, 4)).toBe(3);
    expect(stonesLaid(4, 4)).toBe(6);
  });
});
