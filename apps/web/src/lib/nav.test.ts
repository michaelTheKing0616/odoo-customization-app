import { describe, expect, it } from "vitest";
import { NAV_ITEMS } from "@/lib/nav";
import { isNavItemActive, DEFAULT_NAV_EXPANDED } from "@/lib/nav-storage";

describe("nav IA (UIF-2)", () => {
  it("uses unique icons across nav items", () => {
    const icons = NAV_ITEMS.map((item) => item.icon);
    const unique = new Set(icons);
    expect(unique.size).toBe(icons.length);
  });

  it("defaults Overview + Build + AI expanded; Data, Operate, Govern collapsed", () => {
    expect(DEFAULT_NAV_EXPANDED.overview).toBe(true);
    expect(DEFAULT_NAV_EXPANDED.build).toBe(true);
    expect(DEFAULT_NAV_EXPANDED.ai).toBe(true);
    expect(DEFAULT_NAV_EXPANDED.data).toBe(false);
    expect(DEFAULT_NAV_EXPANDED.operate).toBe(false);
    expect(DEFAULT_NAV_EXPANDED.govern).toBe(false);
  });

  it("activates overview only on exact href match", () => {
    const href = "/connections/abc";
    expect(isNavItemActive(href, href, "overview", "")).toBe(true);
    expect(isNavItemActive(`${href}/builder`, href, "overview", "")).toBe(false);
    expect(isNavItemActive(`${href}/import`, href, "overview", "")).toBe(false);
  });

  it("activates child routes with prefix match", () => {
    const href = "/connections/abc/bulk-suite";
    expect(isNavItemActive(href, href, "bulk-suite", "")).toBe(true);
    expect(isNavItemActive(`${href}/extra`, href, "bulk-suite", "")).toBe(true);
  });
});
