import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { DesignerStudioShell } from "./DesignerStudioShell";
import { DesignerToolsRail } from "./DesignerToolsRail";
import { DesignerLiveCanvas } from "./DesignerLiveCanvas";
import { createRef } from "react";

describe("DesignerStudioShell", () => {
  it("places canvas in the center and tools on the rail", () => {
    render(
      <DesignerStudioShell
        sessionBar={<div data-testid="designer-session-bar">session</div>}
        toolbar={<div>toolbar</div>}
        canvas={<div>canvas-body</div>}
        rail={<div>rail-body</div>}
      />,
    );
    expect(screen.getByTestId("designer-page")).toBeTruthy();
    expect(screen.getByTestId("designer-studio-canvas")).toHaveTextContent("canvas-body");
    expect(screen.getByTestId("designer-tools-rail")).toHaveTextContent("rail-body");
    expect(screen.getByTestId("designer-session-bar")).toBeTruthy();
  });

  it("accepts a compact toolbar slot above the canvas", () => {
    render(
      <DesignerStudioShell
        sessionBar={<div>session</div>}
        toolbar={<div data-testid="designer-studio-toolbar">toolbar</div>}
        canvas={<div>canvas-body</div>}
        rail={<div>rail-body</div>}
      />,
    );
    expect(screen.getByTestId("designer-studio-toolbar")).toBeTruthy();
  });
});

describe("DesignerToolsRail", () => {
  it("renders modification tool tabs", () => {
    render(
      <DesignerToolsRail
        value="fields"
        onValueChange={() => undefined}
        tabs={[
          { id: "fields", label: "Fields", content: <p>palette</p> },
          { id: "properties", label: "Properties", content: <p>inspector</p> },
        ]}
      />,
    );
    expect(screen.getByTestId("designer-tools-rail-inner")).toBeTruthy();
    expect(screen.getByText("Fields")).toBeTruthy();
    expect(screen.getByText("palette")).toBeTruthy();
  });
});

describe("DesignerLiveCanvas", () => {
  it("falls back to the structural Odoo canvas when live is unavailable", () => {
    render(
      <DesignerLiveCanvas
        mode="live"
        onModeChange={() => undefined}
        liveUrl={null}
        iframeRef={createRef<HTMLIFrameElement>()}
        iframeKey={1}
        structural={<div data-testid="form-canvas">structural</div>}
      />,
    );
    expect(screen.getByTestId("designer-structural-canvas")).toBeTruthy();
    expect(screen.getByTestId("form-canvas")).toHaveTextContent("structural");
    expect(screen.queryByTestId("designer-live-iframe")).toBeNull();
  });
});
