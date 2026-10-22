import { describe, expect, it } from "vitest";
import { formatWebsiteError } from "./websiteError";

describe("formatWebsiteError UI-S-14", () => {
  it("maps unsafe gate refusals to what / why / next", () => {
    const parts = formatWebsiteError(
      "Unsafe website HTML refused: <script> is not allowed in website pages",
    );
    expect(parts.what).toMatch(/unsafe gate/i);
    expect(parts.why).toMatch(/script/i);
    expect(parts.next).toMatch(/Remove script|save again/i);
    expect(parts.what).not.toMatch(/—/);
    expect(parts.next).not.toMatch(/—/);
  });

  it("maps missing website module", () => {
    const parts = formatWebsiteError("website module not installed");
    expect(parts.what).toMatch(/Website module/i);
    expect(parts.next).toMatch(/Install Website/i);
  });

  it("maps load failures", () => {
    const parts = formatWebsiteError("Failed to load page");
    expect(parts.what).toMatch(/could not be loaded/i);
    expect(parts.next).toMatch(/pick the page again/i);
  });

  it("maps upload failures", () => {
    const parts = formatWebsiteError("file exceeds 5MB limit");
    expect(parts.what).toMatch(/Image upload/i);
    expect(parts.next).toMatch(/5 MB/i);
  });

  it("never returns a bare string — always what / why / next", () => {
    const parts = formatWebsiteError("weird upstream boom");
    expect(parts.what.length).toBeGreaterThan(5);
    expect(parts.why).toBe("weird upstream boom");
    expect(parts.next.length).toBeGreaterThan(5);
  });
});
