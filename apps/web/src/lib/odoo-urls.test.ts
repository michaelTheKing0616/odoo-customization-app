import { describe, expect, it } from "vitest";
import {
  actionRequiresActiveId,
  odooViewUrl,
  pickStandaloneWindowAction,
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

describe("odooViewUrl", () => {
  it("omits action when null", () => {
    expect(odooViewUrl("http://127.0.0.1:8069", "x_lib_loan", "calendar", null)).toBe(
      "http://127.0.0.1:8069/web#model=x_lib_loan&view_type=calendar",
    );
  });

  it("includes standalone action id", () => {
    expect(odooViewUrl("http://127.0.0.1:8069/", "x_lib_loan", "calendar", 185)).toContain(
      "action=185",
    );
  });
});
