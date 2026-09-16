import { describe, expect, it } from "vitest";
import {
  actionRequiresActiveId,
  checklistOpenHref,
  goldOptionAInspectLink,
  isLocalSandboxUrl,
  odooMenuUrl,
  odooRecordUrl,
  odooViewUrl,
  pickStandaloneWindowAction,
  preferHostListActionId,
} from "./odoo-urls";

describe("actionRequiresActiveId", () => {
  it("detects active_id in domain or context", () => {
    expect(
      actionRequiresActiveId({
        id: 1,
        domain: "[('x_book_id','=',active_id)]",
      }),
    ).toBe(true);
    expect(
      actionRequiresActiveId({
        id: 2,
        context: "{'default_x_book_id': active_id}",
      }),
    ).toBe(true);
    expect(
      actionRequiresActiveId({
        id: 3,
        context: "{'default_res_ids': active_ids}",
      }),
    ).toBe(true);
  });

  it("treats empty standalone actions as safe", () => {
    expect(actionRequiresActiveId({ id: 4, domain: "", context: "{}" })).toBe(false);
    expect(actionRequiresActiveId({ id: 5, requires_active_id: false, domain: "active_id" })).toBe(
      false,
    );
  });
});

describe("pickStandaloneWindowAction", () => {
  const rows = [
    {
      id: 211,
      name: "API Loans",
      view_mode: "list,form,calendar",
      context: "{'default_x_book_id': active_id, 'search_default_x_book_id': active_id}",
      domain: "[('x_book_id','=',active_id)]",
    },
    {
      id: 185,
      name: "Loans",
      view_mode: "list,form,calendar",
      context: "{}",
      domain: null,
    },
    {
      id: 181,
      name: "Library Loan",
      view_mode: "list,form",
      context: "{}",
      domain: null,
    },
  ];

  it("skips related actions even when they match view_mode first alphabetically", () => {
    expect(pickStandaloneWindowAction(rows, "calendar")).toBe(185);
  });

  it("returns null when every action requires active_id", () => {
    expect(pickStandaloneWindowAction([rows[0]!], "calendar")).toBeNull();
  });

  it("prefers view_mode match among standalone", () => {
    expect(pickStandaloneWindowAction(rows, "list")).toBe(185);
  });
});

describe("odooMenuUrl", () => {
  it("opens the app root by menu_id", () => {
    expect(odooMenuUrl("http://127.0.0.1:8069/", 42)).toBe(
      "http://127.0.0.1:8069/web#menu_id=42",
    );
  });

  it("includes the bound window action when known", () => {
    expect(odooMenuUrl("http://127.0.0.1:8069", 42, 185)).toContain("action=185");
    expect(odooMenuUrl("http://127.0.0.1:8069", 42, 185)).toContain("menu_id=42");
  });
});

describe("odooViewUrl", () => {
  it("omits action when null", () => {
    expect(odooViewUrl("http://127.0.0.1:8069", "x_lib_loan", "calendar", null)).toBe(
      "http://127.0.0.1:8069/web#model=x_lib_loan&view_type=calendar",
    );
  });

  it("includes standalone action id", () => {
    expect(odooViewUrl("http://127.0.0.1:8069/", "x_lib_loan", "calendar", 185)).toBe(
      "http://127.0.0.1:8069/odoo/action-185",
    );
  });

  it("prefers quotation window actions for sale.order", () => {
    expect(
      preferHostListActionId(
        [
          { id: 332, name: "Sales Orders", view_mode: "list,form" },
          { id: 334, name: "Quotations", view_mode: "list,form" },
        ],
        "sale.order",
      ),
    ).toBe(334);
  });

  it("includes record id for a form deep-link", () => {
    expect(odooViewUrl("http://127.0.0.1:8069", "x_engagement", "form", null, 44)).toContain(
      "id=44",
    );
  });
});

describe("odooRecordUrl", () => {
  it("prefers Odoo 19 action+record path", () => {
    expect(odooRecordUrl("http://127.0.0.1:8069/", "account.move", 56, 211)).toBe(
      "http://127.0.0.1:8069/odoo/action-211/56",
    );
  });

  it("puts id first on the hash when the action is unknown", () => {
    const url = odooRecordUrl("http://127.0.0.1:8069", "account.move", 56, null);
    expect(url.startsWith("http://127.0.0.1:8069/web#id=56")).toBe(true);
    expect(url).toContain("model=account.move");
    expect(url).toContain("view_type=form");
  });
});

describe("isLocalSandboxUrl", () => {
  it("matches local Docker Odoo on 8069", () => {
    expect(isLocalSandboxUrl("http://127.0.0.1:8069")).toBe(true);
    expect(isLocalSandboxUrl("http://localhost:8069")).toBe(true);
  });

  it("rejects staging and production URLs", () => {
    expect(isLocalSandboxUrl("https://erp.example.com")).toBe(false);
    expect(isLocalSandboxUrl("http://127.0.0.1:8070")).toBe(false);
  });
});

describe("goldOptionAInspectLink", () => {
  it("does not open General Settings when Accounting is missing", () => {
    expect(goldOptionAInspectLink("currency_rate_cbn", "http://127.0.0.1:8069/")).toBeNull();
    expect(
      goldOptionAInspectLink("currency_rate_cbn", "http://127.0.0.1:8069/", {
        hostReady: false,
      }),
    ).toBeNull();
    expect(goldOptionAInspectLink("currency_rate_cbn", null)).toBeNull();
  });

  it("opens Invoicing settings via the account config action after the host is ready", () => {
    const withAction = goldOptionAInspectLink("currency_rate_cbn", "http://127.0.0.1:8069/", {
      hostReady: true,
      href: "http://127.0.0.1:8069/web#action=314&model=res.config.settings&view_type=form",
    });
    expect(withAction?.label).toBe("Open Accounting Settings");
    expect(withAction?.href).toContain("action=314");
    expect(withAction?.hint).toMatch(/Enterprise/i);
    const viaId = goldOptionAInspectLink("currency_rate_cbn", "http://127.0.0.1:8069/", {
      hostReady: true,
      actionId: 314,
    });
    expect(viaId?.href).toMatch(/action[=-]314/);
    expect(viaId?.href).not.toBe(
      "http://127.0.0.1:8069/web#model=res.config.settings&view_type=form",
    );
  });
});

describe("checklistOpenHref", () => {
  it("prefers action id then model, then /web# hints", () => {
    expect(
      checklistOpenHref(
        { action_id: 42, odoo_model: "payment.provider" },
        "http://127.0.0.1:8069",
      ),
    ).toBe("http://127.0.0.1:8069/odoo/action-42");
    expect(
      checklistOpenHref({ odoo_model: "ir.mail_server" }, "http://127.0.0.1:8069"),
    ).toContain("model=ir.mail_server");
    expect(
      checklistOpenHref(
        { href_hint: "/web#action=payment.action_payment_provider&model=payment.provider" },
        "http://127.0.0.1:8069",
      ),
    ).toBe(
      "http://127.0.0.1:8069/web#action=payment.action_payment_provider&model=payment.provider",
    );
    expect(
      checklistOpenHref({ href_hint: "Settings → Technical" }, "http://127.0.0.1:8069"),
    ).toBeNull();
  });
});
