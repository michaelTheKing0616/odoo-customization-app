import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { OdooField } from "./OdooField";
import { OdooKanbanView } from "./OdooKanbanView";
import { OdooChatterStub } from "./OdooChatterStub";
import type { PreviewField, PreviewKanbanView } from "@/lib/draft-form-preview";

describe("OdooField widgets", () => {
  it("renders boolean as square checkbox by default", () => {
    const field: PreviewField = {
      id: "x_active",
      name: "x_active",
      string: "Active",
      ttype: "boolean",
    };
    render(<OdooField field={field} />);
    const el = screen.getByTestId("odoo-widget-boolean-x_active");
    expect(el).toBeTruthy();
    expect(el.getAttribute("data-widget")).toBe("checkbox");
    expect(el.querySelector(".ofp-checkbox")).toBeTruthy();
    expect(el.querySelector(".ofp-toggle")).toBeNull();
    expect(el.textContent || "").not.toMatch(/False|True|checkbox/i);
  });

  it("renders boolean_toggle as pill toggle", () => {
    const field: PreviewField = {
      id: "x_flag",
      name: "x_flag",
      string: "Flag",
      ttype: "boolean",
      widget: "boolean_toggle",
    };
    render(<OdooField field={field} />);
    const el = screen.getByTestId("odoo-widget-boolean-x_flag");
    expect(el.getAttribute("data-widget")).toBe("boolean_toggle");
    expect(el.querySelector(".ofp-toggle")).toBeTruthy();
  });

  it("renders selection dropdown chrome", () => {
    const field: PreviewField = {
      id: "x_status",
      name: "x_status",
      string: "Status",
      ttype: "selection",
      selection: [
        { value: "draft", label: "Draft" },
        { value: "done", label: "Done" },
      ],
    };
    render(<OdooField field={field} />);
    expect(screen.getByTestId("odoo-widget-selection-x_status")).toBeTruthy();
    expect(screen.getByText("Draft")).toBeTruthy();
  });

  it("renders many2one relation chip", () => {
    const field: PreviewField = {
      id: "x_partner_id",
      name: "x_partner_id",
      string: "Customer",
      ttype: "many2one",
    };
    render(<OdooField field={field} />);
    expect(screen.getByTestId("odoo-widget-m2o-x_partner_id")).toBeTruthy();
  });

  it("renders monetary amount", () => {
    const field: PreviewField = {
      id: "x_amount",
      name: "x_amount",
      string: "Amount",
      ttype: "monetary",
    };
    render(<OdooField field={field} />);
    expect(screen.getByTestId("odoo-widget-monetary-x_amount")).toBeTruthy();
  });

  it("renders date widget", () => {
    const field: PreviewField = {
      id: "x_date",
      name: "x_date",
      string: "Date",
      ttype: "date",
    };
    render(<OdooField field={field} />);
    expect(screen.getByTestId("odoo-widget-date-x_date")).toBeTruthy();
  });
  it("never uses the field label as the char sample value", () => {
    const field: PreviewField = {
      id: "x_customer_po_reference",
      name: "x_customer_po_reference",
      string: "Customer PO reference",
      ttype: "char",
    };
    render(<OdooField field={field} />);
    const label = screen.getByText("Customer PO reference");
    expect(label).toBeTruthy();
    const value = screen.getByTestId("odoo-widget-char-x_customer_po_reference");
    expect(value.textContent || "").toBe("Sample");
    expect(value.textContent || "").not.toBe("Customer PO reference");
  });
});

describe("OdooKanbanView", () => {
  it("shows color swatch and kanban state dots", () => {
    const view: PreviewKanbanView = {
      type: "kanban",
      model: "x_ticket",
      title: "Tickets",
      groupBy: "x_status",
      cardFields: [
        { id: "x_name", name: "x_name", string: "Subject" },
        { id: "x_partner_id", name: "x_partner_id", string: "Customer" },
      ],
    };
    render(<OdooKanbanView view={view} />);
    expect(screen.getByTestId("odoo-kanban-view")).toBeTruthy();
    expect(screen.getAllByTestId("odoo-kanban-card").length).toBeGreaterThan(0);
    expect(screen.getAllByTestId("odoo-kanban-state").length).toBeGreaterThan(0);
    expect(screen.getAllByTestId("odoo-kanban-color").length).toBeGreaterThan(0);
  });
});

describe("OdooChatterStub", () => {
  it("renders composer and thread in full density", () => {
    render(<OdooChatterStub density="full" />);
    expect(screen.getByTestId("odoo-chatter-stub")).toBeTruthy();
    expect(screen.getByText(/Write a message/)).toBeTruthy();
  });
});

  it("renders one2many as embedded list columns (not Tag A/B)", () => {
    const field: PreviewField = {
      id: "x_checklist_line_ids",
      name: "x_checklist_line_ids",
      string: "Checklist lines",
      ttype: "one2many",
      relation: "x_demo_checklist_line",
      relationColumns: [
        { name: "x_name", string: "Checklist item", ttype: "char" },
        { name: "x_done", string: "Done", ttype: "boolean" },
      ],
    };
    render(<OdooField field={field} />);
    const el = screen.getByTestId("odoo-widget-o2m-x_checklist_line_ids");
    expect(el).toBeTruthy();
    expect(el.textContent || "").toMatch(/Checklist item/);
    expect(el.textContent || "").toMatch(/Done/);
    expect(el.textContent || "").not.toMatch(/Tag A/);
  });

  it("renders parts used O2M with product + qty columns", () => {
    const field: PreviewField = {
      id: "x_parts_line_ids",
      name: "x_parts_line_ids",
      string: "Parts used",
      ttype: "one2many",
      relationColumns: [
        { name: "x_product_id", string: "Product", ttype: "many2one" },
        { name: "x_qty", string: "Quantity", ttype: "float" },
      ],
    };
    render(<OdooField field={field} />);
    const el = screen.getByTestId("odoo-widget-o2m-x_parts_line_ids");
    expect(el.textContent || "").toMatch(/Product/);
    expect(el.textContent || "").toMatch(/Quantity/);
  });

