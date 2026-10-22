import { describe, expect, it } from "vitest";
import {
  extractTCallTargets,
  refuseRootReplace,
  refuseUnsafeQwebViewArch,
  refuseUnsafeQwebViewSave,
  sanitizeQwebArchForPreview,
} from "./qwebUnsafeGate";

describe("qwebUnsafeGate DOC-QWEB (PDF-05 family)", () => {
  it("allows stock layout t-call and grounded field arch", () => {
    const arch =
      '<t t-call="web.external_layout"><div class="page"><span t-field="doc.name"/></div></t>';
    expect(refuseUnsafeQwebViewArch(arch)).toBeNull();
  });

  it("refuses script / t-raw / XXE / on* / javascript:", () => {
    expect(refuseUnsafeQwebViewArch("<p><script>x</script></p>")).toMatch(/script/i);
    expect(refuseUnsafeQwebViewArch('<div t-raw="object.x"/>')).toMatch(/t-raw/);
    expect(
      refuseUnsafeQwebViewArch(
        '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><p>x</p>',
      ),
    ).toMatch(/external entities|DOCTYPE/);
    expect(refuseUnsafeQwebViewArch('<p onclick="alert(1)">x</p>')).toMatch(/event handlers/);
    expect(refuseUnsafeQwebViewArch('<a href="javascript:alert(1)">x</a>')).toMatch(
      /javascript:/,
    );
  });

  it("grandfathers loaded t-call targets but refuses invent", () => {
    expect(refuseUnsafeQwebViewArch('<t t-call="evil.template"/>')).toMatch(/allowlist/);
    expect(
      refuseUnsafeQwebViewArch('<t t-call="sale.report_saleorder_document"/>', {
        allowExistingTCalls: ["sale.report_saleorder_document"],
      }),
    ).toBeNull();
  });

  it("refuses root replace", () => {
    expect(refuseRootReplace("/", "replace")).toMatch(/root/);
    expect(refuseRootReplace("//div[hasclass('page')]", "inside")).toBeNull();
  });

  it("combined save gate surfaces a clear human error", () => {
    const err = refuseUnsafeQwebViewSave({
      arch: "<script>bad</script>",
      blocks: [{ kind: "paragraph", text: "ok" }],
    });
    expect(err).toMatch(/script/i);
    expect(err).not.toMatch(/Error:|Traceback|stack/i);
  });

  it("extracts t-call targets and sanitizes preview", () => {
    expect(
      extractTCallTargets(
        '<t t-call="web.external_layout"><t t-call="sale.report_saleorder_document"/></t>',
      ),
    ).toEqual(["sale.report_saleorder_document", "web.external_layout"]);
    const out = sanitizeQwebArchForPreview(
      '<p onclick="x"><span t-field="doc.name"/></p><script>bad</script>',
    );
    expect(out).not.toMatch(/script/i);
    expect(out).not.toMatch(/onclick/i);
    expect(out).toMatch(/qweb-field-chip|data-qweb-field/);
  });
});
