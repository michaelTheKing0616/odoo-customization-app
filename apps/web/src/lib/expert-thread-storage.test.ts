import { describe, expect, it, beforeEach } from "vitest";
import {
  clearExpertThread,
  expertThreadStorageKey,
  loadExpertThread,
  saveExpertThread,
} from "./expert-thread-storage";

describe("expert-thread-storage", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("round-trips turns per connection", () => {
    saveExpertThread("c1", [{ role: "user", content: "What is xpath?" }]);
    expect(loadExpertThread("c1")).toEqual([{ role: "user", content: "What is xpath?" }]);
    expect(loadExpertThread("c2")).toEqual([]);
    expect(expertThreadStorageKey("c1")).toBe("expert-thread-c1");
  });

  it("clears and survives corrupt JSON", () => {
    sessionStorage.setItem(expertThreadStorageKey("c1"), "{not-json");
    expect(loadExpertThread("c1")).toEqual([]);
    saveExpertThread("c1", [{ role: "assistant", content: "ok" }]);
    clearExpertThread("c1");
    expect(loadExpertThread("c1")).toEqual([]);
  });
});
