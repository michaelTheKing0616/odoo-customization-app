import { describe, expect, it } from "vitest";
import { NAV_ITEMS } from "@/lib/nav";
import { isNavItemActive, DEFAULT_NAV_EXPANDED } from "@/lib/nav-storage";

describe("nav IA (UIF-2)", () => {
  it("uses unique icons across sidebar-visible nav items", () => {
    const visible = NAV_ITEMS.filter((item) => item.shipped !== false && item.sidebar !== false);
    const icons = visible.map((item) => item.icon);
    const unique = new Set(icons);
    expect(unique.size).toBe(icons.length);
  });

  it("defaults Overview + Build + AI + Operations expanded; Data + Govern collapsed", () => {
    expect(DEFAULT_NAV_EXPANDED.overview).toBe(true);
    expect(DEFAULT_NAV_EXPANDED.build).toBe(true);
    expect(DEFAULT_NAV_EXPANDED.ai).toBe(true);
    expect(DEFAULT_NAV_EXPANDED.data).toBe(false);
    expect(DEFAULT_NAV_EXPANDED.operate).toBe(true);
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

  it("AI Studio sidebar includes App Studio, Draft Studio, Job Autopilot, and Projects", () => {
    const aiSidebar = NAV_ITEMS.filter(
      (item) => item.group === "ai" && item.shipped !== false && item.sidebar !== false,
    );
    expect(aiSidebar.map((item) => item.id)).toEqual([
      "app-studio",
      "wizard",
      "job-autopilot",
      "projects",
    ]);
  });

  it("keeps ModuleSpec / Expert as deep-link routes outside the AI sidebar", () => {
    const demoted = ["modulespec", "expert"];
    for (const id of demoted) {
      const item = NAV_ITEMS.find((n) => n.id === id);
      expect(item, id).toBeTruthy();
      expect(item!.sidebar).toBe(false);
      expect(item!.shipped).not.toBe(false);
    }
  });

  it("places Live Demo Co-Pilot first under Operations and keeps it sidebar-visible", () => {
    const item = NAV_ITEMS.find((n) => n.id === "live-demo-copilot");
    expect(item?.group).toBe("operate");
    expect(item?.sidebar).not.toBe(false);
    const operateSidebar = NAV_ITEMS.filter(
      (n) => n.group === "operate" && n.shipped !== false && n.sidebar !== false,
    );
    expect(operateSidebar[0]?.id).toBe("live-demo-copilot");
  });
});
