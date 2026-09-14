import { describe, expect, it } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { StudioProgress } from "@/components/studio/StudioProgress";
import { StudioBusyLabel } from "@/components/studio/StudioBusyLabel";

describe("App Studio loaders", () => {
  it("shows the infinity loop on the generating screen", () => {
    render(<StudioProgress label="Authoring Option A module" detail="Sales markup" />);
    const screenRoot = screen.getByTestId("studio-progress");
    expect(screenRoot.querySelector(".studio-loader-infinity")).not.toBeNull();
    expect(screenRoot.querySelector(".spinner")).toBeNull();
    expect(screen.getByText("Authoring Option A module")).toBeTruthy();
    cleanup();
  });

  it("shows spokes next to busy button copy", () => {
    render(<StudioBusyLabel>Starting…</StudioBusyLabel>);
    expect(document.querySelector(".studio-loader-spokes")).not.toBeNull();
    expect(screen.getByText("Starting…")).toBeTruthy();
    cleanup();
  });
});
