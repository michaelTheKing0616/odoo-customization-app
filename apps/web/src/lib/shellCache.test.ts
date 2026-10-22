import { describe, expect, it } from "vitest";
import { readShell, scrub, writeShell } from "./shellCache";

describe("shell cache (touch 142)", () => {
  it("never keeps credentials", () => {
    expect(scrub({ name: "A", password: "x", api_key: "y", nested: [{ token: "t", id: 1 }] })).toEqual({ name: "A", nested: [{ id: 1 }] });
  });
  it("round-trips", () => {
    writeShell("connection:a", { id: "a", name: "Shop" });
    expect(readShell("connection:a")).toEqual({ id: "a", name: "Shop" });
  });
});
