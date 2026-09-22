import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BuildSpineBar } from "./BuildSpineBar";

describe("BuildSpineBar", () => {
  it("renders mode chips and honesty", () => {
    render(
      <BuildSpineBar
        connectionId="c1"
        activeMode="option_a"
        payload={{
          version: 1,
          prompt: "markup",
          brief: "markup",
          build_mode: "option_a",
          chips: [],
          delivery_lane: "module_sh_or_self",
          artifact_kind: "option_a_module",
          honesty: "One Build entry — test honesty.",
        }}
      />,
    );
    expect(screen.getByTestId("build-spine-bar")).toHaveAttribute("data-build-mode", "option_a");
    expect(screen.getByTestId("build-spine-honesty").textContent).toMatch(/One Build entry/);
    expect(screen.getByTestId("build-spine-stamps").textContent).toMatch(/module_sh_or_self/);
    expect(screen.getByTestId("build-spine-chip-option_a")).toHaveAttribute("data-active", "1");
    expect(screen.getByTestId("build-spine-surfaces")).toBeTruthy();
  });
});
