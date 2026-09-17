import { describe, expect, it } from "vitest";
import {
  detectHostingKind,
  hostingHint,
  normalizeOdooBaseUrl,
  suggestDbFromUrl,
  odooApiKeyDocsUrl,
  odooApiKeyGuideUrl,
} from "./odoo-hosting";

describe("odoo-hosting", () => {
  it("strips Online UI paths and fragments", () => {
    expect(normalizeOdooBaseUrl("https://acme.odoo.com/odoo/discuss")).toBe(
      "https://acme.odoo.com",
    );
    expect(normalizeOdooBaseUrl("https://acme.odoo.com/web#action=1")).toBe(
      "https://acme.odoo.com",
    );
    expect(normalizeOdooBaseUrl("acme.odoo.com")).toBe("https://acme.odoo.com");
  });

  it("detects hosting kinds and suggests Online db", () => {
    expect(detectHostingKind("https://acme.odoo.com/odoo")).toBe("online");
    expect(detectHostingKind("https://proj.odoo.sh")).toBe("odoo_sh");
    expect(detectHostingKind("http://127.0.0.1:8069")).toBe("self_hosted");
    expect(suggestDbFromUrl("https://acme.odoo.com/odoo")).toBe("acme");
    expect(hostingHint("online")).toMatch(/API key/i);
  });
});

  it("builds Open-in-Odoo API key entry URLs", () => {
    expect(odooApiKeyGuideUrl("https://acme.odoo.com/odoo")).toBe(
      "https://acme.odoo.com/odoo",
    );
    expect(odooApiKeyGuideUrl("http://127.0.0.1:8069")).toBe(
      "http://127.0.0.1:8069/web",
    );
    expect(odooApiKeyDocsUrl(19)).toContain("19.0");
  });

