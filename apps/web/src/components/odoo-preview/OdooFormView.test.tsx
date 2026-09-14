import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { OdooFormView } from "./OdooFormView";
import type { PreviewFormView } from "@/lib/draft-form-preview";

const SAMPLE: PreviewFormView = {
  type: "form",
  model: "x_helpdesk_ticket",
  title: "Helpdesk Ticket",
  statusbar: {
    field: "x_status",
    stages: ["new", "in_progress", "done"],
    activeStage: "new",
  },
  headerButtons: [{ id: "confirm", string: "Confirm", variant: "primary" }],
  smartButtons: [{ id: "tasks", string: "Tasks", count: 3 }],
  groups: [
    {
      id: "identity",
      string: "Identity",
      columns: 2,
      fields: [
        { id: "x_name", name: "x_name", string: "Subject", ttype: "char" },
        { id: "x_partner_id", name: "x_partner_id", string: "Customer", ttype: "many2one" },
      ],
    },
    {
      id: "details",
      string: "Details",
      columns: 2,
      fields: [{ id: "x_priority", name: "x_priority", string: "Priority", ttype: "selection" }],
    },
  ],
  groupLayout: "two-column",
  chatter: "stub",
};

describe("OdooFormView", () => {
  it("renders statusbar, groups, stat button, and chatter stub", () => {
    render(<OdooFormView view={SAMPLE} />);
    expect(screen.getByTestId("odoo-statusbar")).toBeTruthy();
    expect(screen.getByTestId("odoo-form-groups")).toBeTruthy();
    expect(screen.getByTestId("odoo-button-box")).toBeTruthy();
    expect(screen.getByTestId("odoo-chatter-stub")).toBeTruthy();
    expect(screen.getByText("Confirm")).toBeTruthy();
    expect(screen.getByTestId("odoo-field-x_name")).toBeTruthy();
    expect(screen.getByTestId("odoo-widget-char-x_name")).toBeTruthy();
    expect(screen.getByTestId("odoo-widget-m2o-x_partner_id")).toBeTruthy();
  });
});
