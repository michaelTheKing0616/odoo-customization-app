import { describe, expect, it } from "vitest";
import { normalizeScanValue, scanFindDomain } from "./scanUtils";

describe("scanUtils", () => {
  it("trims scanned values", () => {
    expect(normalizeScanValue("  ABC-9  ")).toBe("ABC-9");
  });

  it("builds Odoo domain triple for find", () => {
    expect(scanFindDomain("x_barcode", "QR1")).toEqual(["x_barcode", "=", "QR1"]);
  });
});
