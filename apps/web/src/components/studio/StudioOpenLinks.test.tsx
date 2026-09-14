/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { StudioOpenInViewDesigner } from "./StudioOpenLinks";

afterEach(() => cleanup());

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
