import { describe, expect, it } from "vitest";
import { connectionIdFromPath } from "./useConfirmTarget";

describe("92 confirm target", () => {
  it("reads the connection from the path", () => {
    expect(connectionIdFromPath("/connections/abc/menus")).toBe("abc");
    expect(connectionIdFromPath("/settings")).toBeNull();
    expect(connectionIdFromPath("/connections/new")).toBeNull();
  });
});

import { testCopyStatus } from "./craft";
describe("saved test-copy flag", () => {
  it("flag wins; old rows guess from the name, marked uncertain", () => {
    expect(testCopyStatus({ name: "Acme staging", is_test_copy: false })).toEqual({ test: false, certain: true });
    expect(testCopyStatus({ name: "Acme", is_test_copy: true })).toEqual({ test: true, certain: true });
    expect(testCopyStatus({ name: "Acme staging" })).toEqual({ test: true, certain: false });
    expect(testCopyStatus({ name: "Acme", is_test_copy: null })).toEqual({ test: false, certain: false });
  });
});
