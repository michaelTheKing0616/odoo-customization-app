import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { INGENIUM_ICONS } from "./ingeniumIcons";

describe("Ingenium icons (touch 98)", () => {
  it("are outlined on the Lucide grid (99)", () => {
    for (const [name, Icon] of Object.entries(INGENIUM_ICONS)) {
      const { container } = render(<Icon />);
      const svg = container.querySelector("svg")!;
      expect(svg.getAttribute("viewBox"), name).toBe("0 0 24 24");
      expect(svg.getAttribute("fill")).toBe("currentColor");
      expect(svg.querySelector("path")?.getAttribute("d")?.length).toBeGreaterThan(100);
    }
  });
});
