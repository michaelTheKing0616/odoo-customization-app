import { describe, expect, it } from "vitest";
import {
  fallbackWidgetsForTtype,
  IMAGE_SIZE_PRESETS,
  modifierToMode,
  modeToModifier,
} from "./widgetCatalog";
import {
  domainRulesToString,
  parseDomainString,
} from "@/components/DomainBuilder";

describe("modifierToMode / modeToModifier", () => {
  it("maps off / always / domain", () => {
    expect(modifierToMode(undefined)).toBe("off");
    expect(modifierToMode(false)).toBe("off");
    expect(modifierToMode(true)).toBe("always");
    expect(modifierToMode("1")).toBe("always");
    expect(modifierToMode("[('state', '=', 'draft')]")).toBe("domain");
  });

  it("round-trips modes", () => {
    expect(modeToModifier("off", "[]")).toBeUndefined();
    expect(modeToModifier("always", "[]")).toBe(true);
    expect(modeToModifier("domain", "[('x_status', '=', 'done')]")).toBe(
      "[('x_status', '=', 'done')]",
    );
    // Empty domain cannot round-trip through value alone (UI pins When… open).
    expect(modeToModifier("domain", "[]")).toBeUndefined();
    expect(modifierToMode(undefined)).toBe("off");
  });

  it("treats non-empty domain strings as When mode", () => {
    expect(modifierToMode("[('state', '=', 'posted')]")).toBe("domain");
    expect(modifierToMode("[]")).toBe("domain"); // literal [] is still a string domain token
  });
});

describe("widget catalog fallbacks", () => {
  it("exposes curated widgets per ttype", () => {
    expect(fallbackWidgetsForTtype("char").map((w) => w.id)).toEqual(
      expect.arrayContaining(["email", "phone", "url", "barcode"]),
    );
    expect(fallbackWidgetsForTtype("selection").map((w) => w.id)).toEqual(
      expect.arrayContaining(["radio", "priority"]),
    );
    expect(fallbackWidgetsForTtype("binary").map((w) => w.id)).toEqual(
      expect.arrayContaining(["image", "signature"]),
    );
    expect(fallbackWidgetsForTtype("unknown")).toEqual([]);
  });

  it("has image size presets", () => {
    expect(IMAGE_SIZE_PRESETS.length).toBeGreaterThanOrEqual(3);
    expect(IMAGE_SIZE_PRESETS.some((p) => p.options.includes("128"))).toBe(true);
  });
});

describe("domain builder helpers (Field properties Invisible)", () => {
  it("serializes AND rules", () => {
    expect(
      domainRulesToString([
        { field: "x_status", op: "=", value: "done" },
        { field: "active", op: "=", value: "True" },
      ]),
    ).toContain("x_status");
    expect(domainRulesToString([{ field: "", op: "=", value: "" }])).toBe("[]");
  });

  it("parses simple domains back", () => {
    const rules = parseDomainString("[('state', '=', 'draft')]");
    expect(rules[0]?.field).toBe("state");
    expect(rules[0]?.op).toBe("=");
    expect(rules[0]?.value).toBe("draft");
  });
});
