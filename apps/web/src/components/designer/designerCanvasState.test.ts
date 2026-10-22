import { describe, expect, it } from "vitest";
import {
  canvasStateCopy,
  classifyDesignerError,
  explainXmlReason,
  isPreviewStale,
  viewErrorLine,
  type DesignerCanvasState,
} from "./designerCanvasState";

describe("UI-S-12 designer canvas states", () => {
  it("reads the line from lxml and Odoo view errors", () => {
    expect(
      viewErrorLine("Opening and ending tag mismatch: group line 9 and form, line 14, column 8"),
    ).toBe(14);
    expect(viewErrorLine("Error while validating view near: {'line': 22}")).toBe(22);
    expect(viewErrorLine("Field x_foo does not exist")).toBeNull();
  });

  it("classifies invalid XML with line and a clean reason", () => {
    const state = classifyDesignerError(
      "XMLSyntaxError: Opening and ending tag mismatch: group line 9 and form, line 14, column 8",
    );
    expect(state).toEqual({
      kind: "xml-invalid",
      line: 14,
      reason: "Opening and ending tag mismatch: group line 9 and form",
    });
  });

  it("classifies inherit conflicts and extracts the locator", () => {
    const state = classifyDesignerError(
      "Element '<xpath expr=\"//field[@name='x_partner_id']\">' cannot be located in parent view",
    );
    expect(state?.kind).toBe("inherit-conflict");
    expect(state && state.kind === "inherit-conflict" ? state.locator : null).toBe(
      "//field[@name='x_partner_id']",
    );
  });

  it("leaves unrelated failures to the page error notice", () => {
    expect(classifyDesignerError("Network error")).toBeNull();
    expect(classifyDesignerError("")).toBeNull();
    expect(classifyDesignerError(null)).toBeNull();
  });

  it("caps very long reasons", () => {
    const state = classifyDesignerError(`Invalid XML: ${"x".repeat(400)}`);
    expect(state && state.kind === "xml-invalid" ? state.reason.length : 0).toBeLessThanOrEqual(180);
  });

  it("marks the live preview stale only when live is showing and the canvas is dirty", () => {
    expect(isPreviewStale({ mode: "live", liveAvailable: true, dirty: true })).toBe(true);
    expect(isPreviewStale({ mode: "live", liveAvailable: true, dirty: false })).toBe(false);
    expect(isPreviewStale({ mode: "structure", liveAvailable: true, dirty: true })).toBe(false);
    expect(isPreviewStale({ mode: "live", liveAvailable: false, dirty: true })).toBe(false);
  });

  it("writes plain copy: line in the title, alert vs status roles, no em dashes", () => {
    const states: DesignerCanvasState[] = [
      { kind: "xml-invalid", line: 14, reason: "Tag mismatch." },
      { kind: "xml-invalid", line: null, reason: "Tag mismatch." },
      { kind: "inherit-conflict", locator: "//field[@name='x']", reason: "r" },
      { kind: "inherit-conflict", locator: null, reason: "r" },
      { kind: "preview-stale" },
    ];
    const copies = states.map(canvasStateCopy);
    expect(copies[0].title).toContain("line 14");
    expect(copies[0].role).toBe("alert");
    expect(copies[2].code).toBe("//field[@name='x']");
    expect(copies[4].role).toBe("status");
    for (const c of copies) {
      expect(`${c.title} ${c.text}`).not.toMatch(/\u2014/);
    }
  });

  it("explains common lxml messages in plain words and keeps Odoo's text as code", () => {
    expect(explainXmlReason("Opening and ending tag mismatch: group line 9 and form")).toBe(
      "The <group> opened on line 9 is still open when </form> closes. Close the <group> first.",
    );
    expect(explainXmlReason("Premature end of data in tag sheet line 3")).toContain("never closed");
    expect(explainXmlReason("Extra content at the end of the document")).toContain("one root element");
    expect(explainXmlReason("Opening and ending tag mismatch: page line 4 and notebook.")).toBe(
      "The <page> opened on line 4 is still open when </notebook> closes. Close the <page> first.",
    );
    expect(explainXmlReason("Field x_foo does not exist")).toBeNull();

    const copy = canvasStateCopy({
      kind: "xml-invalid",
      line: 14,
      reason: "Opening and ending tag mismatch: group line 9 and form",
    });
    expect(copy.text).toMatch(/^The <group> opened on line 9/);
    expect(copy.code).toBe("Opening and ending tag mismatch: group line 9 and form");
    expect(copy.codeLabel).toBe("Odoo's message");

    const raw = canvasStateCopy({ kind: "xml-invalid", line: null, reason: "Tag mismatch." });
    expect(raw.text).toContain("Tag mismatch.");
    expect(raw.code).toBeNull();
  });
});
