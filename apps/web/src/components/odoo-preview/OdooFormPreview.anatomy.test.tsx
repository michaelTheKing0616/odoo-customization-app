/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { OdooControlPanel } from "./OdooControlPanel";
import { OdooFormView } from "./OdooFormView";
import { CUSTOMER_HEALTH_FORM, CUSTOMER_HEALTH_PLAN } from "./fixtures/customer-health";
import { deferredIntegrationsOf } from "@/lib/integration-plan";

afterEach(cleanup);

function renderForm() {
  return render(
    <OdooFormView
      view={CUSTOMER_HEALTH_FORM}
      deferredIntegrations={deferredIntegrationsOf(CUSTOMER_HEALTH_PLAN)}
    />,
  );
}

describe("Odoo form preview anatomy", () => {
  it("renders header buttons left and arrow stages right with the current stage", () => {
    renderForm();
    const header = screen.getByTestId("odoo-form-header");
    expect(within(header).getByText("Recompute score")).toBeTruthy();
    const stages = within(screen.getByTestId("odoo-statusbar")).getAllByRole("listitem");
    expect(stages.map((s) => s.textContent)).toEqual(["Healthy", "Watch", "At risk", "Churned"]);
    expect(stages[1].getAttribute("aria-current")).toBe("step");
    expect(stages[0].getAttribute("aria-current")).toBeNull();
  });

  it("renders oe_title from the name field with a placeholder, not inside a group", () => {
    renderForm();
    const title = screen.getByTestId("odoo-form-title");
    expect(within(title).getByText("Account name")).toBeTruthy();
    expect(screen.getByTestId("odoo-widget-char-x_name").textContent).toBe("e.g. Account name");
    const groups = screen.getByTestId("odoo-form-groups");
    expect(within(groups).queryByTestId("odoo-field-x_name")).toBeNull();
  });

  it("splits one long group into two inner columns and keeps every field", () => {
    renderForm();
    const groups = screen.getByTestId("odoo-form-groups");
    expect(groups.className).toContain("is-two-column");
    expect(screen.getByTestId("odoo-group-main")).toBeTruthy();
    expect(screen.getByTestId("odoo-group-main__col2")).toBeTruthy();
    for (const name of ["x_partner_id", "x_score", "x_risk_level", "x_renewal_date", "x_arr", "x_tag_ids", "x_auto_alert"]) {
      expect(screen.getByTestId(`odoo-field-${name}`)).toBeTruthy();
    }
  });

  it("renders field types the Odoo way", () => {
    renderForm();
    const m2o = screen.getByTestId("odoo-widget-m2o-x_partner_id");
    expect(m2o.querySelector(".ofp-caret")).toBeTruthy();
    expect(m2o.querySelector(".ofp-m2o-open")).toBeTruthy();
    expect(screen.getByTestId("odoo-widget-tags-x_tag_ids").querySelectorAll(".ofp-tag")).toHaveLength(2);
    expect(screen.getByTestId("odoo-widget-selection-x_risk_level").textContent).toContain("Low");
    expect(screen.getByTestId("odoo-widget-boolean-x_auto_alert").querySelector(".ofp-checkbox")).toBeTruthy();
    expect(screen.getByTestId("odoo-widget-date-x_renewal_date").querySelector(".ofp-date-icon")).toBeTruthy();
    expect(screen.getByTestId("odoo-widget-monetary-x_arr").textContent).toContain("$");
    expect(screen.getByTestId("odoo-widget-number-x_score").textContent).toBe("0");
    const partnerRow = screen.getByTestId("odoo-field-x_partner_id").closest(".ofp-field");
    expect(partnerRow?.className).toContain("is-required");
    expect(partnerRow?.querySelector(".ofp-type-hint")?.textContent).toBe("Link to one record");
  });

  it("renders the notebook with a one2many list, Add a line, and switches tabs", () => {
    renderForm();
    const nb = screen.getByTestId("odoo-notebook-nb");
    const o2m = within(nb).getByTestId("odoo-widget-o2m-x_signal_ids");
    expect(o2m.querySelectorAll("thead th")).toHaveLength(4);
    expect(o2m.querySelectorAll("tbody tr")).toHaveLength(2);
    expect(o2m.textContent).toContain("Add a line");
    fireEvent.click(within(nb).getByRole("tab", { name: "Success plan" }));
    expect(within(nb).getByTestId("odoo-widget-html-x_plan_notes")).toBeTruthy();
    expect(within(nb).getByRole("tab", { name: "Success plan" }).getAttribute("aria-selected")).toBe("true");
  });

  it("renders smart buttons with counts and the chatter", () => {
    renderForm();
    const box = screen.getByTestId("odoo-button-box");
    expect(within(box).getByText("Expansion opportunities")).toBeTruthy();
    expect(within(box).getByText("3")).toBeTruthy();
    const chatter = screen.getByTestId("odoo-chatter-stub");
    for (const label of ["Send message", "Log note", "Activities", "Today"]) {
      expect(within(chatter).getByText(label)).toBeTruthy();
    }
  });

  it("marks left out and deferred apps on the sheet", () => {
    renderForm();
    const deferred = screen.getByTestId("odoo-form-deferred");
    expect(within(deferred).getByText("Helpdesk")).toBeTruthy();
    expect(within(deferred).getByText("Left out")).toBeTruthy();
    expect(within(deferred).getByText("Install later")).toBeTruthy();
  });

  it("control panel shows New, breadcrumb and a record pager", () => {
    render(<OdooControlPanel breadcrumb="Customer Success / Customer Health" />);
    const cp = screen.getByTestId("odoo-control-panel");
    expect(within(cp).getByText("New")).toBeTruthy();
    expect(within(cp).getByText("Customer Health").className).toContain("ofp-breadcrumb-current");
    expect(within(cp).getByText("1 / 1")).toBeTruthy();
  });

  it("copy has no em dashes", () => {
    const { container } = renderForm();
    expect(container.textContent || "").not.toMatch(/\u2014/);
  });
});
