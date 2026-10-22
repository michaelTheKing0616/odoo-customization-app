import { describe, expect, it } from "vitest";
import {
  EMPTY_CTA,
  FLEET_STEPS,
  FLEET_TILES,
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  PRIMARY_CTA,
  emptyFleetGuide,
  errorFleetGuide,
  fleetHasEmDash,
  fleetHonestyGuide,
  idleFleetGuide,
  loadingFleetGuide,
  partialFleetGuide,
  primaryCtaForFleet,
  sanitizeFleetCopy,
  stepForFleetState,
} from "./fleetCommandScreen";

describe("fleetCommandScreen", () => {
  it("keeps fleet copy free of em dashes and fake metrics tone", () => {
    const blobs = [
      PAGE_TITLE,
      PAGE_DESCRIPTION,
      PRIMARY_CTA,
      EMPTY_CTA,
      ...FLEET_STEPS,
      ...FLEET_TILES.flatMap((t) => [t.title, t.detail, t.emptyLabel]),
      ...Object.values(fleetHonestyGuide()),
      ...Object.values(idleFleetGuide()),
      ...Object.values(emptyFleetGuide()),
      ...Object.values(errorFleetGuide()),
      ...Object.values(loadingFleetGuide()),
      ...Object.values(partialFleetGuide("Failed jobs")),
    ];
    for (const text of blobs) {
      expect(fleetHasEmDash(text)).toBe(false);
      expect(sanitizeFleetCopy(text)).toBe(text);
    }
    expect(PAGE_DESCRIPTION.toLowerCase()).not.toMatch(/98\.7%|records today/);
  });

  it("names Open a client as the idle primary and Connect Odoo when empty", () => {
    expect(PRIMARY_CTA).toBe("Open a client");
    expect(primaryCtaForFleet(3)).toBe(PRIMARY_CTA);
    expect(primaryCtaForFleet(0)).toBe(EMPTY_CTA);
    expect(primaryCtaForFleet(null)).toBe(PRIMARY_CTA);
  });

  it("lists four fleet tiles with independent count URLs", () => {
    expect(FLEET_TILES).toHaveLength(4);
    const ids = FLEET_TILES.map((t) => t.id);
    expect(new Set(ids).size).toBe(4);
    for (const tile of FLEET_TILES) {
      expect(tile.countUrl).toMatch(/^\/api\/command\/tiles\//);
    }
  });

  it("honesty guide states multi-connection read-only scope", () => {
    const honesty = fleetHonestyGuide();
    expect(honesty.why.toLowerCase()).toMatch(/every connection|whole fleet|workspace/);
    expect(honesty.why.toLowerCase()).toMatch(/never writes?/);
    expect(honesty.next.toLowerCase()).toMatch(/one client|connection/);
  });

  it("stage index advances from fleet to inspect", () => {
    expect(stepForFleetState({ clientCount: 0, hasTileError: false, loading: false })).toBe(1);
    expect(stepForFleetState({ clientCount: 2, hasTileError: false, loading: false })).toBe(2);
    expect(stepForFleetState({ clientCount: 2, hasTileError: true, loading: false })).toBe(2);
    expect(stepForFleetState({ clientCount: null, hasTileError: false, loading: true })).toBe(1);
  });

  it("sanitizeFleetCopy replaces unicode dashes", () => {
    expect(sanitizeFleetCopy("A—B–C")).toBe("A-B-C");
  });
});
