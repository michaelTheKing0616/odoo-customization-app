import { describe, expect, it } from "vitest";
import {
  isFragile,
  isPositional,
  preferSemanticCandidates,
  scoreLocator,
  semanticInjectExpr,
} from "./xpathLocator";

describe("xpathLocator", () => {
  it("scores named locators above positional ones", () => {
    expect(scoreLocator("//field[@name='partner_id']")).toBeGreaterThan(
      scoreLocator("//sheet/group[2]/field[1]"),
    );
    expect(isPositional("//group[1]")).toBe(true);
    expect(isPositional("//field[@name='email']")).toBe(false);
    expect(isFragile("//group[@string='Other']")).toBe(true);
    expect(isFragile("//group[@id='header_left_group']")).toBe(false);
  });

  it("prefers named group inject when the parent has a unique id", () => {
    const arch = `
      <form>
        <sheet>
          <group id="header_left_group"><field name="partner_id"/></group>
          <group string="Other"><field name="ref"/></group>
        </sheet>
      </form>
    `;
    expect(semanticInjectExpr(arch, "form")).toBe("//group[@id='header_left_group']");
    expect(semanticInjectExpr(null, "form")).toBe("//sheet");
    expect(
      semanticInjectExpr(
        '<form><sheet><group><field name="x"/></group></sheet></form>',
        "form",
      ),
    ).toBe("//group");
  });

  it("ranks overlay candidates by score", () => {
    const ranked = preferSemanticCandidates([
      { xpath: "//sheet/group[2]/field[1]" },
      { xpath: "//group[@id='header_left_group']//field[@name='partner_id']" },
    ]);
    expect(ranked[0].xpath).toContain("@id=");
  });
});
