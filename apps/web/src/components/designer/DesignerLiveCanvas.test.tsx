import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { createRef } from "react";
import { DesignerLiveCanvas } from "./DesignerLiveCanvas";

afterEach(() => cleanup());

function renderCanvas(props: Partial<Parameters<typeof DesignerLiveCanvas>[0]> = {}) {
  return render(
    <DesignerLiveCanvas
      mode="structure"
      onModeChange={() => undefined}
      liveUrl={null}
      iframeRef={createRef<HTMLIFrameElement>()}
      iframeKey={1}
      structural={<div data-testid="card">card</div>}
      {...props}
    />,
  );
}

describe("DesignerLiveCanvas (UI-S-12)", () => {
  it("puts the structural card on the desk and reports mode with aria-pressed", () => {
    renderCanvas();
    expect(screen.getByTestId("designer-structural-canvas")).toContainElement(
      screen.getByTestId("card"),
    );
    expect(screen.getByTestId("designer-canvas-mode-structure")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByTestId("designer-canvas-mode-live")).toBeDisabled();
    expect(screen.queryByTestId("designer-canvas-state")).toBeNull();
  });

  it("renders an XML error with its line as an alert and runs the action", () => {
    const onClick = vi.fn();
    renderCanvas({
      canvasState: {
        kind: "xml-invalid",
        line: 14,
        reason: "Opening and ending tag mismatch.",
        action: { label: "Open Advanced", onClick },
      },
    });
    const state = screen.getByTestId("designer-canvas-state");
    expect(state).toHaveAttribute("data-state", "xml-invalid");
    expect(state).toHaveAttribute("role", "alert");
    expect(state).toHaveTextContent("line 14");
    fireEvent.click(screen.getByTestId("designer-canvas-state-action"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("shows the failing inherit locator as code", () => {
    renderCanvas({
      canvasState: {
        kind: "inherit-conflict",
        locator: "//field[@name='x_partner_id']",
        reason: "cannot be located in parent view",
      },
    });
    expect(screen.getByTestId("designer-canvas-state-locator")).toHaveTextContent(
      "//field[@name='x_partner_id']",
    );
  });

  it("announces a stale preview politely", () => {
    renderCanvas({ canvasState: { kind: "preview-stale" } });
    expect(screen.getByTestId("designer-canvas-state")).toHaveAttribute("role", "status");
  });

  it("glosses a known XML error in plain words and keeps Odoo's message as code", () => {
    renderCanvas({
      canvasState: {
        kind: "xml-invalid",
        line: 14,
        reason: "Opening and ending tag mismatch: group line 9 and form",
      },
    });
    expect(screen.getByTestId("designer-canvas-state")).toHaveTextContent(
      "The <group> opened on line 9 is still open",
    );
    expect(screen.getByTestId("designer-canvas-state-code")).toHaveTextContent(
      "Opening and ending tag mismatch: group line 9 and form",
    );
  });

  it("tags the live frame as the last saved version while the preview is stale", () => {
    renderCanvas({
      mode: "live",
      liveUrl: "/proxy/x",
      canvasState: { kind: "preview-stale" },
    });
    expect(screen.getByTestId("designer-live-stale-tag")).toHaveTextContent("Last saved version");
  });

  it("switches modes from the segmented control", () => {
    const onModeChange = vi.fn();
    renderCanvas({ liveUrl: "/proxy/x", onModeChange });
    fireEvent.click(screen.getByTestId("designer-canvas-mode-live"));
    expect(onModeChange).toHaveBeenCalledWith("live");
  });
});
