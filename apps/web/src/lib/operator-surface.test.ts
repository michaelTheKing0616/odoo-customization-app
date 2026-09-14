import { describe, expect, it } from "vitest";
import {
  operatorSurfaceFromDraft,
  operatorSurfaceHasPlacement,
} from "./operator-surface";

describe("operatorSurfaceFromDraft", () => {
  it("reads host buttons and stock links", () => {
    const surface = operatorSurfaceFromDraft({
      _operator_surface: {
        app_menu: { label: "Punch Card", technical_name: "root_punch_card" },
        host_buttons: [
          {
            host_model: "res.partner",
            host_label: "Contacts",
            button_label: "Punch Cards",
            residual_model: "x_punch_card",
          },
        ],
        residual_buttons: [],
        stock_links: [
          {
            field: "x_partner_id",
            field_label: "Customer",
            stock_model: "res.partner",
            stock_label: "Contacts",
            on_model: "x_punch_card",
          },
        ],
        summary: "Open Punch Card. Also on stock forms: Punch Cards on Contacts.",
      },
    });
    expect(surface).not.toBeNull();
    expect(surface!.app_menu?.label).toBe("Punch Card");
    expect(surface!.host_buttons[0].host_label).toBe("Contacts");
    expect(surface!.stock_links[0].field_label).toBe("Customer");
    expect(operatorSurfaceHasPlacement(surface)).toBe(true);
  });

  it("returns null when missing", () => {
    expect(operatorSurfaceFromDraft({})).toBeNull();
    expect(operatorSurfaceHasPlacement(null)).toBe(false);
  });
});
