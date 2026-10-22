/** @vitest-environment jsdom */
import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { OperateStudioBar } from "./OperateStudioBar";

afterEach(() => cleanup());

describe("OperateStudioBar", () => {
  it("folds honesty into the studio bar", () => {
    render(
      <div className="op-studio-shell">
        <div className="op-studio">
          <OperateStudioBar
            testIdPrefix="script-runner"
            badge={{ label: "Idle", variant: "default" }}
            honesty={{
              title: "Sandbox only",
              why: "Runs stay inside the sandbox.",
              next: "Paste a script, then Run.",
            }}
          />
        </div>
      </div>,
    );
    expect(screen.getByTestId("script-runner-studio-bar")).toBeInTheDocument();
    expect(screen.getByTestId("script-runner-honesty-title")).toHaveTextContent(/Sandbox only/i);
    expect(screen.getByTestId("script-runner-honesty-why")).toBeInTheDocument();
  });
});
