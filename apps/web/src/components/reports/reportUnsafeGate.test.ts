import { describe, expect, it } from "vitest";
import {
  QWEB_T_CALL_ALLOWLIST,
  refuseUnsafeBlockText,
  refuseUnsafeQwebArch,
  refuseUnsafeReportDesign,
} from "./reportUnsafeGate";

describe("reportUnsafeGate PDF-05", () => {
  it("allowlist includes stock layouts", () => {
    expect(QWEB_T_CALL_ALLOWLIST.has("web.external_layout")).toBe(true);
    expect(QWEB_T_CALL_ALLOWLIST.has("web.html_container")).toBe(true);
  });

  it("refuses t-raw", () => {
    expect(refuseUnsafeQwebArch('<div t-raw="doc.x"/>')).toMatch(/t-raw/);
  });

  it("refuses script any case", () => {
    expect(refuseUnsafeQwebArch("<SCRIPT>alert(1)</SCRIPT>")).toMatch(/script/i);
  });

  it("refuses DOCTYPE / ENTITY XXE", () => {
    expect(
      refuseUnsafeQwebArch('<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'),
    ).toMatch(/external entities|DOCTYPE/);
  });

  it("refuses non-allowlisted t-call", () => {
    expect(refuseUnsafeQwebArch('<t t-call="evil.payload"/>')).toMatch(/allowlist/);
    expect(refuseUnsafeQwebArch('<t t-call="web.external_layout"/>')).toBeNull();
  });

  it("refuses block text that looks like QWeb", () => {
    expect(
      refuseUnsafeBlockText([{ type: "heading", text: '<t t-esc="doc.name"/>' }]),
    ).toMatch(/must not contain QWeb/);
    expect(refuseUnsafeBlockText([{ type: "text", text: "{{ x }}" }])).toMatch(
      /must not contain QWeb/,
    );
    expect(refuseUnsafeBlockText([{ type: "text", text: "Plain thank-you note" }])).toBeNull();
  });

  it("combined design gate surfaces a clear human error", () => {
    const err = refuseUnsafeReportDesign({
      blocks: [{ type: "text", text: "ok" }],
      arch: '<t t-name="x"><script/></t>',
    });
    expect(err).toMatch(/script/i);
    expect(err).not.toMatch(/Error:|Traceback|stack/i);
  });
});
