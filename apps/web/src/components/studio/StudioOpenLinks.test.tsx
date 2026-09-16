/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { StudioOpenInOdoo, StudioOpenInViewDesigner } from "./StudioOpenLinks";

afterEach(() => cleanup());

describe("StudioOpenInOdoo", () => {
  it("enables the link after Option A promote onto an inherit host", () => {
    render(
      <StudioOpenInOdoo
        goldOptionA={false}
        goldCanOpenSettings={false}
        goldInspect={null}
        appIsLiveOnOdoo
        openInOdooUrl="http://127.0.0.1:8069/web#model=sale.order&view_type=list"
        fieldPack
        hostFormName="Quotation"
        liveAppName="Sales markup"
        testId="open-in-odoo"
      />,
    );
    const link = screen.getByTestId("open-in-odoo");
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute(
      "href",
      "http://127.0.0.1:8069/web#model=sale.order&view_type=list",
    );
    expect(link).toHaveTextContent("Open in Odoo");
  });

  it("stays disabled until live with a URL", () => {
    render(
      <StudioOpenInOdoo
        goldOptionA={false}
        goldCanOpenSettings={false}
        goldInspect={null}
        appIsLiveOnOdoo={false}
        openInOdooUrl={null}
        fieldPack={false}
        hostFormName="Ticket"
        liveAppName="Helpdesk"
        testId="open-in-odoo"
      />,
    );
    expect(screen.getByTestId("open-in-odoo")).toBeDisabled();
  });
});

describe("StudioOpenInViewDesigner", () => {
  it("deep-links the primary x_* model", () => {
    render(
      <StudioOpenInViewDesigner
        href="/connections/c1/designer?model=x_ticket"
        designerModel="x_ticket"
        appIsLiveOnOdoo
        fieldPack={false}
        hostFormName="Ticket"
        testId="open-view-designer"
      />,
    );
    const link = screen.getByTestId("open-view-designer");
    expect(link).toHaveAttribute("href", "/connections/c1/designer?model=x_ticket");
    expect(link.textContent).toBe("Open in View Designer");
  });
});
