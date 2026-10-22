import { describe, expect, it } from "vitest";
import {
  refuseUnsafeWebsiteBlocks,
  refuseUnsafeWebsiteHtml,
  refuseUnsafeWebsiteSave,
  sanitizeWebsiteHtmlForPreview,
} from "./websiteUnsafeGate";

describe("websiteUnsafeGate DOC-WEBSITE (PDF-05 family)", () => {
  it("allows plain website HTML and locked t-foreach", () => {
    expect(refuseUnsafeWebsiteHtml("<section><p>Hello</p></section>")).toBeNull();
    expect(
      refuseUnsafeWebsiteHtml('<t t-foreach="items" t-as="item"><span t-esc="item"/></t>'),
    ).toBeNull();
  });

  it("reuses report gate: refuses script / t-raw / XXE / bad t-call", () => {
    expect(refuseUnsafeWebsiteHtml("<p><script>x</script></p>")).toMatch(/script/i);
    expect(refuseUnsafeWebsiteHtml('<div t-raw="object.x"/>')).toMatch(/t-raw/);
    expect(
      refuseUnsafeWebsiteHtml(
        '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><p>x</p>',
      ),
    ).toMatch(/external entities|DOCTYPE/);
    expect(refuseUnsafeWebsiteHtml('<t t-call="evil.payload"/>')).toMatch(/allowlist/);
  });

  it("refuses on* handlers and javascript: URLs", () => {
    expect(refuseUnsafeWebsiteHtml('<p onclick="alert(1)">x</p>')).toMatch(/event handlers/);
    expect(refuseUnsafeWebsiteHtml('<a href="javascript:alert(1)">x</a>')).toMatch(
      /javascript:/,
    );
  });

  it("refuses QWeb invent in editable text and bad href/src", () => {
    expect(
      refuseUnsafeWebsiteBlocks([
        { id: "p-1", kind: "paragraph", text: '<t t-esc="doc.name"/>' },
      ]),
    ).toMatch(/QWeb|Unsafe website/);
    expect(
      refuseUnsafeWebsiteBlocks([
        { id: "a-1", kind: "link", text: "Go", href: "javascript:alert(1)" },
      ]),
    ).toMatch(/javascript:/);
    expect(
      refuseUnsafeWebsiteBlocks([
        { id: "img-1", kind: "image", src: "javascript:alert(1)" },
      ]),
    ).toMatch(/javascript:/);
  });

  it("gates locked_xml on the same family (no second unsafe editor)", () => {
    expect(
      refuseUnsafeWebsiteBlocks([
        { id: "locked-1", kind: "locked", locked_xml: "<script>evil</script>" },
      ]),
    ).toMatch(/script/i);
  });

  it("combined save gate surfaces a clear human error", () => {
    const err = refuseUnsafeWebsiteSave({
      blocks: [{ id: "p-1", kind: "paragraph", text: "ok" }],
      arch: "<section><script>bad</script></section>",
    });
    expect(err).toMatch(/script/i);
    expect(err).not.toMatch(/Error:|Traceback|stack/i);
  });

  it("allows grounded editable blocks", () => {
    expect(
      refuseUnsafeWebsiteBlocks([
        {
          id: "sec-1",
          kind: "section",
          children: [
            { id: "h-1", kind: "heading", text: "Welcome" },
            { id: "p-1", kind: "paragraph", text: "Hello" },
            { id: "a-1", kind: "link", text: "Go", href: "/contact" },
            { id: "img-1", kind: "image", src: "/web/image/1" },
            {
              id: "locked-1",
              kind: "locked",
              locked_xml: '<t t-foreach="items" t-as="item"/>',
            },
          ],
        },
      ]),
    ).toBeNull();
  });

  it("preview sanitize strips script and on*", () => {
    const out = sanitizeWebsiteHtmlForPreview(
      '<p onclick="x">Hi</p><script>bad</script><a href="javascript:1">x</a>',
    );
    expect(out).not.toMatch(/script/i);
    expect(out).not.toMatch(/onclick/i);
    expect(out).not.toMatch(/javascript:/i);
  });
});
