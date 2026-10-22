import { describe, expect, it } from "vitest";
import {
  collectMailPlaceholderFields,
  formatMailPlaceholder,
  refuseUnsafeMailHtml,
  refuseUnsafeMailSubject,
  refuseUnsafeMailTemplate,
  sanitizeMailHtmlForPreview,
} from "./mailUnsafeGate";

describe("mailUnsafeGate DOC-MAIL (PDF-05 family)", () => {
  it("allows plain HTML + grounded Jinja placeholders", () => {
    const html = "<p>Hello {{ object.name }}</p>";
    expect(
      refuseUnsafeMailHtml(html, { knownFields: ["name", "email"] }),
    ).toBeNull();
  });

  it("reuses report gate: refuses script / t-raw / XXE", () => {
    expect(refuseUnsafeMailHtml("<p><script>x</script></p>")).toMatch(/script/i);
    expect(refuseUnsafeMailHtml('<div t-raw="object.x"/>')).toMatch(/t-raw/);
    expect(
      refuseUnsafeMailHtml('<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><p>x</p>'),
    ).toMatch(/external entities|DOCTYPE/);
  });

  it("refuses on* handlers and javascript: URLs", () => {
    expect(refuseUnsafeMailHtml('<p onclick="alert(1)">x</p>')).toMatch(/event handlers/);
    expect(refuseUnsafeMailHtml('<a href="javascript:alert(1)">x</a>')).toMatch(/javascript:/);
  });

  it("refuses ungrounded invent when schema is known", () => {
    expect(
      refuseUnsafeMailHtml("<p>{{ object.x_made_up }}</p>", {
        knownFields: ["name"],
      }),
    ).toMatch(/unknown field 'x_made_up'/);
  });

  it("combined template gate surfaces a clear human error", () => {
    const err = refuseUnsafeMailTemplate({
      subject: "Hi {{ object.name }}",
      body_html: "<script>bad</script>",
      knownFields: ["name"],
    });
    expect(err).toMatch(/script/i);
    expect(err).not.toMatch(/Error:|Traceback|stack/i);
  });

  it("subject gate refuses unknown fields", () => {
    expect(
      refuseUnsafeMailSubject("Hi {{ object.ghost }}", { knownFields: ["name"] }),
    ).toMatch(/unknown field 'ghost'/);
  });

  it("collects Jinja and legacy placeholders", () => {
    expect(
      collectMailPlaceholderFields("{{ object.name }} and ${object.email}"),
    ).toEqual(["name", "email"]);
  });

  it("formats grounded placeholders", () => {
    expect(formatMailPlaceholder("display_name")).toBe("{{ object.display_name }}");
  });

  it("preview sanitize strips script and chips placeholders", () => {
    const out = sanitizeMailHtmlForPreview(
      '<p onclick="x">Hi {{ object.name }}</p><script>bad</script>',
    );
    expect(out).not.toMatch(/script/i);
    expect(out).not.toMatch(/onclick/i);
    expect(out).toMatch(/mail-ph/);
    expect(out).toMatch(/object\.name/);
  });
});
