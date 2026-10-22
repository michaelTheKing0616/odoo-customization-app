/** @vitest-environment happy-dom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ScriptRunnerStateGuide } from "./ScriptRunnerStateGuide";
import { scriptRunnerHonestyGuide } from "@/lib/scriptRunnerScreen";

afterEach(() => cleanup());

describe("ScriptRunnerStateGuide", () => {
  it("renders what / why / next and strips em dashes", () => {
    render(
      <ScriptRunnerStateGuide
        testId="script-runner-honesty"
        tone="warning"
        guide={{
          title: "Title — with dash",
          why: "Why – detail",
          next: "Next step",
        }}
      />,
    );
    expect(screen.getByTestId("script-runner-honesty-title")).toHaveTextContent("Title - with dash");
    expect(screen.getByTestId("script-runner-honesty-why")).toHaveTextContent("Why - detail");
    expect(screen.getByTestId("script-runner-honesty-next")).toHaveTextContent("Next step");
  });

  it("shows the honesty guide copy", () => {
    render(
      <ScriptRunnerStateGuide
        testId="script-runner-honesty"
        tone="warning"
        guide={scriptRunnerHonestyGuide()}
      />,
    );
    expect(screen.getByTestId("script-runner-honesty-title").textContent?.toLowerCase()).toContain(
      "no test run",
    );
  });
});
