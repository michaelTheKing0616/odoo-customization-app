/** @vitest-environment jsdom */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DesignerUiProvider, useDesignerUi } from "./DesignerUiContext";

function Probe() {
  const { railTab, designerV2Shell } = useDesignerUi();
  return (
    <div data-testid="probe">
      {railTab}:{designerV2Shell ? "v2" : "off"}
    </div>
  );
}

describe("DesignerUiProvider", () => {
  it("provides rail tab and v2 shell flag", () => {
    render(
      <DesignerUiProvider railTab="properties" setRailTab={() => {}} designerV2Shell>
        <Probe />
      </DesignerUiProvider>,
    );
    expect(screen.getByTestId("probe")).toHaveTextContent("properties:v2");
  });
});
